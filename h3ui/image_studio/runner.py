"""Persistent FIFO image jobs, exact submission reconciliation and output identity."""
import copy
import hashlib
import json
import secrets
import threading
import time
from pathlib import Path
from PIL import Image
from .store import uid, encode
from . import compiler, inputs
from ..studio_store import Conflict
from ..comfy import ComfyError, ComfyCancelled
from ..studio_progress import ProgressWatch
from ..generation.recovery import resolve_submission

ACTIVE=('waiting','submitting','running','unknown')


def error_fields(exc):
    raw = str(exc)
    explicit = getattr(exc, 'error_kind', None)
    if explicit in ('network', 'engine', 'website'): kind = explicit
    elif isinstance(exc, Conflict): kind = 'conflict'
    elif isinstance(exc, KeyError): kind = 'not_found'
    elif isinstance(exc, ComfyError):
        kind = 'network' if raw.startswith('ComfyUI request ') or raw.startswith('Timed out waiting ') else 'engine'
    elif isinstance(exc, (TimeoutError, ConnectionError)): kind = 'network'
    elif isinstance(exc, ValueError): kind = 'input'
    else: kind = 'website'
    return dict(note=raw, error_kind=kind, error_raw=raw)


def history_error(status):
    raw = json.dumps(status, ensure_ascii=False)
    messages = status.get('messages', [])
    details = [str(item[1]['exception_message']) for item in messages
               if isinstance(item, (list, tuple)) and len(item)>1 and isinstance(item[1], dict) and item[1].get('exception_message')]
    return dict(note='引擎执行失败：'+('；'.join(details) if details else raw), error_kind='engine', error_raw=raw)


class ImageProgress(ProgressWatch):
    def phase(self,node):
        kind=self.graph.get(node,{}).get('class_type','')
        if kind=='KSampler':return '采样生成'
        if kind=='VAEDecode':return '解码图片'
        if kind=='SaveImage':return '保存图片'
        if 'Loader' in kind:return '加载模型'
        return '准备图片与编辑条件'


class Runner:
    def __init__(self,service):
        self.s=service;self.store=service.store;self.st=service.st
        self.lock=threading.RLock();self.thread=None

    def gpu_guard(self,kind,pid):
        unresolved=[r for r in self.store.all('runs') if r['state'] in ('submitting','running','unknown')]
        return not unresolved or (kind=='image_recover' and all(r['project']==pid for r in unresolved))

    def submit(self,pid,tid,revision,key):
        if self.s.cfg.get('studio_disable_generation'):raise ValueError('该开发环境禁止提交生成任务')
        if not isinstance(key,str) or not key or len(key)>100:raise ValueError('缺少本次操作标记')
        with self.store.lock:
            prior=next((r for r in self.store.all('runs',pid) if r.get('request_key')==key),None)
            if prior:return prior
            p=self.store.project(pid)
            if p['revision']!=revision:raise Conflict('请先保存当前草稿')
            if any(r['state'] in ACTIVE for r in self.store.all('runs',pid)):raise Conflict('本项目已有运行或待确认提交')
            pre=self.s.preflight(pid,tid)
            if not pre['ready']:raise ValueError('；'.join(pre['errors']))
            task=self.store.get('tasks',tid,pid)
            seed=task['settings']['seed'] if task['settings']['seed'] is not None else secrets.randbelow(2**53)
            task=copy.deepcopy(task);task['settings']['seed']=seed
            snapshot=copy.deepcopy(task)
            snapshot['inputs']={role:self.store.get('inputs',task[role],pid) for role in (*compiler.active_slots(task), *(['mask'] if task['submode']=='region' else [])) if task.get(role)} if task['submode']!='text' else {}
            if task['submode']=='text':snapshot.update(A=None,B=None,mask=None,adapter_revision=compiler.TEXT_ADAPTER_REVISION)
            if task['submode']=='dual' and any(task.get(slot) for slot in compiler.IMAGE_SLOTS[2:]):snapshot['multi_reference_revision']=compiler.MULTIREF_REVISION
            run=dict(id=uid(),project=pid,task=tid,state='waiting',created=time.time(),seed=seed,snapshot=snapshot,
                     geometry=pre['geometry'],
                     source_revision=revision,request_key=key,source_hash=compiler.SOURCE_HASH,plugin_version=compiler.PLUGIN_VERSION,
                     note='等待生成通道',prompt_id=None)
            self.store.put('runs',run)
        self.wake()
        return run

    def wake(self):
        if self.s.cfg.get('studio_disable_generation'):return
        with self.lock:
            if self.thread and self.thread.is_alive():return
            self.thread=threading.Thread(target=self.dispatch,daemon=True)
            self.thread.start()

    def dispatch(self):
        try:
            self._dispatch()
        finally:
            with self.lock:
                self.thread=None
                runs=self.store.all('runs')
                if any(r['state']=='waiting' for r in runs) and not any(r['state'] in ('submitting','running','unknown') for r in runs):
                    self.wake()

    def _dispatch(self):
        while True:
            runs=self.store.all('runs')
            uncertain=next((r for r in runs if r['state'] in ('submitting','running','unknown')),None)
            run=uncertain or next(iter(sorted((r for r in runs if r['state']=='waiting'),key=lambda x:x['created'])),None)
            if not run:return
            kind='image_recover' if uncertain else 'image_generate'
            lease=self.st.jobs._reserve(kind,run['project'],lane='gpu')
            if lease is None:
                if uncertain:return
                time.sleep(3);continue
            try:
                # A user may close/cancel the queued record after selection but
                # before this lease is acquired. Never resurrect that snapshot.
                run=self.store.get('runs',run['id'])
                if run['state'] not in ACTIVE:continue
                uncertain=run['state'] in ('submitting','running','unknown')
                if uncertain:
                    self.reconcile(run)
                    if self.store.get('runs',run['id'])['state']=='unknown':return
                else:self.execute(run)
            except Exception as exc:
                current=self.store.get('runs',run['id'])
                if current['state']=='cancelled':continue
                if isinstance(exc,ComfyCancelled):
                    self.update(run,state='cancelled',note=str(exc),finished=time.time(),error_kind=None,error_raw=None)
                    continue
                state='unknown' if current['state'] in ('submitting','running','unknown') else 'failed'
                self.update(run,state=state,**error_fields(exc))
                if state=='unknown':return
            finally:self.st.jobs._release(lease)

    def update(self,run,**fields):
        now=time.time()
        def apply(record):
            if fields.get('state') in ('success','failed','cancelled'):
                fields.setdefault('finished',record.get('finished') or now)
            record.update(**fields,updated=now)
        return self.store.mutate('runs',run['id'],apply)

    def execute(self,run):
        if self.store.get('runs',run['id'])['state']!='waiting':return
        queue=self.st.comfy._get('/queue',timeout=10)
        if queue.get('queue_running') or queue.get('queue_pending'):
            self.update(run,note='等待ComfyUI中的其他任务完成');time.sleep(3);return
        with self.store.lock:
            current=self.store.get('runs',run['id'])
            if current['state']!='waiting':return
            self.update(run,started=current.get('started') or time.time(),note='准备图片与工作流')
        catalog=self.s.catalog(sync=True)
        if catalog['node_catalog']['error']:
            exc = ComfyError(catalog['node_catalog']['error'])
            exc.error_kind = catalog['node_catalog'].get('error_kind') or 'website'
            raise exc
        t=run['snapshot']
        missing=catalog.get('missing_by_tool',{}).get(t['submode'],catalog['missing'])
        if missing:raise ValueError('缺少节点，请正常重启ComfyUI加载插件：'+', '.join(missing))
        if t['submode']=='dual' and any(t.get(slot) for slot in compiler.IMAGE_SLOTS[2:]) and catalog.get('multi_reference_nodes_missing'):
            raise ValueError('3—9图编辑需要加载随网站提供的 timeforest_krea_multiref 扩展节点；安装说明见 comfyui_nodes/README.md。缺少：'+', '.join(catalog['multi_reference_nodes_missing']))
        engine_models=json.loads((self.st.root/'image-catalog.json').read_text(encoding='utf-8'))['models']
        for role in compiler.model_roles(t['submode']):
            name=t['models'][role]
            if name not in engine_models[role]:
                raise ValueError('引擎没有所选模型：'+name)
        directory=self.store.directory(run['project'])/'image_runs'/run['id'];directory.mkdir(parents=True,exist_ok=True)
        prepared=inputs.execution_inputs(self.store,run['project'],t,directory/'inputs')
        # Engine receives private execution copies, never the original library files.
        import shutil
        engine=self.st.input/'time-forest-images'/run['id'];engine.mkdir(parents=True,exist_ok=True)
        names={}
        for role,path in prepared.items():
            target=engine/(role+'.png');shutil.copyfile(path,target)
            names[role]=target.relative_to(self.st.input).as_posix()
        graph,output=compiler.compile_graph(t['submode'],t['prompt'],names,t['settings'],t['models'],prefix='time-forest/images/'+run['id'])
        graph_hash=hashlib.sha256(encode(graph).encode()).hexdigest()
        (directory/'workflow.json').write_text(encode(graph),encoding='utf-8')
        (directory/'manifest.json').write_text(encode(run),encoding='utf-8')
        with self.store.lock:
            if self.store.get('runs',run['id'])['state']!='waiting':return
            self.update(run,state='submitting',graph_hash=graph_hash,output_node=output,note='正在提交')
        identity='time-forest-'+run['id']
        watch=ImageProgress(self.st.comfy.url,identity,graph,directory,directory,0).start()
        try:
            prompt_id=self.st.comfy.submit(graph,identity)
            self.update(run,state='running',prompt_id=prompt_id,note='正在生成')
            watch.submitted(prompt_id)
            record=self.st.comfy.wait(prompt_id)
            self.finish(self.store.get('runs',run['id']),record)
        finally:watch.close()

    def reconcile(self,run):
        directory=self.store.directory(run['project'])/'image_runs'/run['id']
        prompt_id,history,queued=resolve_submission(self.st.comfy,{**run,'directory':str(directory)})
        self.update(run,prompt_id=prompt_id)
        if history.get(prompt_id,{}).get('status',{}).get('status_str')=='error':
            self.update(run,state='failed',**history_error(history[prompt_id]['status']));return
        if history.get(prompt_id,{}).get('status',{}).get('status_str')=='success':
            self.finish(self.store.get('runs',run['id']),history);return
        if queued:
            self.update(run,state='running',note='已找到原任务，等待完成',error_kind=None,error_raw=None)
            self.finish(self.store.get('runs',run['id']),self.st.comfy.wait(prompt_id));return
        self.update(run,state='unknown',note='无法确认原提交结果；不会重复生成，请保留记录并核对引擎历史')

    def finish(self,run,history):
        record=history.get(run['prompt_id'],{})
        if record.get('status',{}).get('status_str')=='error':
            self.update(run,state='failed',**history_error(record['status']));return
        if record.get('status',{}).get('status_str')!='success':raise ValueError('尚未取得成功执行记录')
        items=record.get('outputs',{}).get(run['output_node'],{}).get('images',[])
        if len(items)!=1:raise ValueError('本次输出数量不符合一张图片的配方')
        item=items[0]
        if item.get('type')!='output':raise ValueError('引擎输出不是已保存图片')
        source=self.st.comfy.output_path(item,self.st.output)
        with Image.open(source) as image:
            image.load();w,h=image.size
        t=run['snapshot'];a=t['inputs'].get('A',{'width':0,'height':0})
        if [w,h]!=compiler.geometry(t['submode'],a['width'],a['height'],t['settings'])['output']:
            raise ValueError('实际输出尺寸与本次几何计划不一致')
        dest=self.store.directory(run['project'])/'image_runs'/run['id']/'result.png'
        import shutil
        shutil.copyfile(source,dest)
        oid=run['id'] # one immutable output per run, idempotent recovery
        previous=next((o for o in self.store.all('outputs',run['project']) if o['id']==oid),{})
        out={**previous, 'id':oid,'project':run['project'],'task':run['task'],'run':run['id'],'path':str(dest),
             'width':w,'height':h,'hash':hashlib.sha256(dest.read_bytes()).hexdigest(),'created':run['created']}
        self.store.put('outputs',out)
        self.update(run,state='success',note='图片已生成',finished=time.time(),error_kind=None,error_raw=None)

    def cancel(self,pid,rid):
        with self.store.lock:
            run=self.store.get('runs',rid,pid)
            if run['state']=='waiting':return self.update(run,state='cancelled',note='已取消等待')
            if run['state'] in ACTIVE:
                return self.update(run,note='已停止后续安排；当前引擎任务仍会完成，结果保留。未调用全局中断。')
            return run
