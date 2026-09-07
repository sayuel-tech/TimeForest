"""Image projects: draft transactions, immutable runs, trusted asset transfers."""
import copy
import hashlib
import json
import time
import ipaddress
from pathlib import Path
from urllib.parse import urlparse
from .store import ImageStore, uid, encode
from . import compiler, inputs
from .parameters import PARAMETER_CONTRACT_VERSION, public_parameters
from .runner import error_fields
from ..generation.local_models import LocalModels
from ..studio_store import Conflict
from ..studio_progress import write


class ImageStudio:
    def __init__(self, studio, library):
        self.st, self.lib = studio, library
        self.cfg = studio.ctx['cfg']
        self.store = ImageStore(studio.root)
        self.models = {**compiler.MODELS, **self.cfg.get('image_models', {})}
        self.local_models = LocalModels(self.cfg)
        self._local_catalog = None
        from .runner import Runner
        self.runner = Runner(self)
        studio.jobs.gpu_guards.append(self.runner.gpu_guard)

    def catalog(self, sync=False):
        """File refresh is local; explicit node sync is scoped to this engine URL."""
        path = self.st.root/'image-catalog.json'
        url = self.st.comfy.url.rstrip('/')
        error = None; error_kind = None
        try:
            cache = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(cache, dict): raise ValueError('节点缓存格式无效')
            if not isinstance(cache.get('models'), dict) or any(not isinstance(v, list) or any(not isinstance(n, str) for n in v) for v in cache['models'].values()):
                raise ValueError('节点模型缓存格式无效')
            if cache.get('url') != url:
                error = '节点缓存未记录当前引擎地址；请按需同步节点能力。'
                error_kind = 'website'
                cache = {}
        except FileNotFoundError: cache = {}
        except (OSError, ValueError) as exc: cache = {}; error = str(exc); error_kind = 'website'
        node_source = 'cache' if cache else 'none'
        if sync:
            try:
                nodes = self.st.comfy._get('/object_info', timeout=15)
                if not isinstance(nodes, dict) or not nodes: raise ValueError('引擎未返回有效节点声明')
                required = set(compiler.WIDGETS)-{'ResolutionSelector','CLIPTextEncode'}
                fresh = dict(url=url, checked=time.time(), missing=sorted(required-set(nodes)), models={})
                for role, ct, field in [('unet','UNETLoader','unet_name'), ('clip','CLIPLoader','clip_name'),
                                        ('vae','VAELoader','vae_name'), ('lora','LoraLoaderModelOnly','lora_name')]:
                    values = nodes.get(ct,{}).get('input',{}).get('required',{}).get(field,[[]])[0]
                    fresh['models'][role] = [v for v in values if isinstance(v, str)] if isinstance(values, list) else []
                fresh['node_types'] = sorted(nodes)
                write(path, fresh)
                cache = fresh; error = None; error_kind = None; node_source = 'online'
            except Exception as exc:
                error = str(exc)
                kind = error_fields(exc)['error_kind']
                # Invalid engine declarations and local cache failures are website
                # operations, not user parameters or presumed network failures.
                error_kind = kind if kind in ('network', 'engine') else 'website'
        host = urlparse(url).hostname
        try: is_local = host == 'localhost' or ipaddress.ip_address(host or '').is_loopback
        except ValueError: is_local = False
        if is_local:
            try:
                scanned = self.local_models.scan()
                meta = scanned['local_models']
                choices = {role: scanned[key] for role, key in [('unet','models'), ('clip','clips'), ('vae','vaes'), ('lora','loras')]}
                # A partial scan keeps last known names; it never changes saved task selections.
                if meta['errors'] and self._local_catalog:
                    choices = {role: sorted(set(values+self._local_catalog['choices'][role]), key=str.casefold) for role, values in choices.items()}
                    meta = {**meta, 'source': 'filesystem_partial', 'cached_at': self._local_catalog['meta']['updated']}
                if not meta['errors']: self._local_catalog = copy.deepcopy(dict(choices=choices, meta=meta))
            except Exception as exc:
                previous = self._local_catalog or dict(choices={r: [] for r in self.models}, meta={})
                choices = copy.deepcopy(previous['choices'])
                meta = dict(source='filesystem_cache' if self._local_catalog else 'filesystem_unavailable',
                            updated=previous['meta'].get('updated'), roots=previous['meta'].get('roots', {}), errors=[str(exc)])
        else:
            choices = {role: cache.get('models', {}).get(role, []) for role in self.models}
            meta = dict(source='remote_online' if node_source=='online' else 'remote_cache' if cache else 'remote_unavailable', updated=cache.get('checked'), roots={}, errors=[],
                        note='远程引擎不使用本机模型目录；列表来自该引擎的节点同步缓存。')
        meta = {**meta, 'engine_url': url}
        return dict(tools=compiler.TOOLS, defaults=compiler.DEFAULTS, models=self.models, choices=choices,
                    parameter_contract_version=PARAMETER_CONTRACT_VERSION, parameters=public_parameters(), local_models=meta,
                    quick_ingest_preserves_selection=True,
                    task_discard_version=1,
                    text_to_image_version=compiler.TEXT_ADAPTER_REVISION,
                    missing_by_tool={tool:sorted(compiler.required_nodes(tool)-set(cache['node_types'])) for tool in compiler.TOOLS} if 'node_types' in cache else {},
                    node_catalog=dict(source=node_source, updated=cache.get('checked'), error=error, error_kind=error_kind, engine_url=url),
                    checked=cache.get('checked'), missing=cache.get('missing'), source_hash=compiler.SOURCE_HASH,
                    plugin_version=compiler.PLUGIN_VERSION, generation_verified=False)

    def create(self, name, submode='single'):
        if submode not in compiler.TOOLS: raise ValueError('图片工具不支持')
        pid, tid = uid(), uid()
        p = dict(id=pid, project=pid, kind='image', mode='image_assets', name=str(name or '图片资产')[:120],
                 revision=1, current_task=tid, created=time.time(), updated=time.time())
        task = dict(id=tid, project=pid, name='编辑任务 1', submode=submode, prompt='', A=None, B=None, mask=None,
                    settings=copy.deepcopy(compiler.DEFAULTS), models=dict(self.models), revision=1)
        with self.store.lock, self.store.connect() as db:
            self.store.put('projects',p,db); self.store.put('tasks',task,db)
        self.store.directory(pid).mkdir(exist_ok=True)
        return self.snapshot(pid)

    def url(self, pid, path):
        file = Path(path).resolve(); root = self.store.directory(pid).resolve()
        if root not in file.parents: raise ValueError('图片文件路径越界')
        return f'/api/v5/projects/{pid}/files/'+file.relative_to(root).as_posix()

    def snapshot(self, pid):
        p = self.store.project(pid)
        p.update(image_contract_version=1, tasks=self.store.all('tasks',pid), inputs=self.store.all('inputs',pid),
                 runs=self.store.all('runs',pid), outputs=self.store.all('outputs',pid))
        p['tasks']=[t for t in p['tasks'] if not t.get('discarded_at')]
        visible={t['id'] for t in p['tasks']}
        p['runs']=[r for r in p['runs'] if r['task'] in visible]
        p['outputs']=[o for o in p['outputs'] if o['task'] in visible]
        p['busy'] = any(r['state'] in ('waiting','submitting','running','unknown') for r in p['runs'])
        for item in p['inputs']+p['outputs']:
            item['url'] = self.url(pid,item['path']); item.pop('path',None)
        for run in p['runs']:
            run.pop('graph',None)
            try: run['progress'] = json.loads((self.store.directory(pid)/'image_runs'/run['id']/'progress.json').read_text(encoding='utf-8'))
            except (OSError,ValueError): pass
        return p

    def summaries(self, trash=False):
        result=[]
        for p in self.store.all('projects'):
            if bool(p.get('deleted_at')) != trash: continue
            tasks=[t for t in self.store.all('tasks',p['id']) if not t.get('discarded_at')]
            visible={t['id'] for t in tasks}
            outputs=[o for o in self.store.all('outputs',p['id']) if not o.get('removed_at') and o['task'] in visible]; runs=self.store.all('runs',p['id'])
            busy=any(r['state'] in ('waiting','submitting','running','unknown') for r in runs)
            cover=next((x for x in outputs if x.get('selected')), outputs[-1] if outputs else None)
            if not cover: cover=next((x for x in self.store.all('inputs',p['id']) if not x.get('mask') and any(x['id']==t.get('A') for t in tasks)),None)
            result.append({**p,'tasks':len(tasks),'outputs':len(outputs),'selected':sum(bool(x.get('selected')) for x in outputs),
                           'cover':self.url(p['id'],cover['path']) if cover else None,'busy':busy,'status':'generating' if busy else 'draft'})
        return result

    def trash(self,pid,data):
        with self.store.lock:
            p=self.store.project(pid,deleted=True)
            if self.store.all('runs',pid) and any(r['state'] in ('waiting','submitting','running','unknown') for r in self.store.all('runs',pid)):
                raise Conflict('本项目还有运行或待确认提交，请先处理')
            if p['revision']!=data.get('revision'): raise Conflict('项目已更新，请刷新')
            p.update(deleted_at=None if data.get('restore') else time.time(),revision=p['revision']+1)
            self.store.put('projects',p)
            return dict(id=pid,revision=p['revision'],deleted=bool(p['deleted_at']))

    def plan(self,pid,data):
        with self.store.lock:
            self.store.project(pid)
            previous={t['id']:t for t in self.store.all('tasks',pid)}
            tasks=[]; seen=set()
            for raw in data.get('tasks',[]):
                tid=raw.get('id')
                if not isinstance(tid,str) or not tid or len(tid)>64 or tid in seen: raise ValueError('任务ID无效或重复')
                seen.add(tid)
                if raw.get('submode') not in compiler.TOOLS: raise ValueError('图片工具无效')
                old=previous.get(tid)
                if old and old.get('discarded_at'):raise Conflict('编辑任务已废弃，请先从回收站恢复')
                if not old:
                    with self.store.connect() as db:
                        if db.execute('SELECT 1 FROM image_tasks WHERE id=?',(tid,)).fetchone():
                            raise ValueError('任务ID已被其他项目使用')
                history=[r for r in self.store.all('runs',pid) if r['task']==tid]
                if old and old['submode']!=raw['submode'] and history: raise Conflict('有历史结果的任务换工具请创建新任务')
                task={k:copy.deepcopy(raw.get(k)) for k in ('name','submode','prompt','A','B','mask')}
                task.update(id=tid,project=pid,name=str(task.get('name') or '编辑任务')[:120],
                            prompt=str(task.get('prompt') or '')[:20000],settings=compiler.settings(raw.get('settings')),
                            models={**self.models,**{k:str(v) for k,v in raw.get('models',{}).items() if k in self.models}},
                            revision=(old or {}).get('revision',0)+1)
                for value in task['models'].values():
                    if not value or Path(value).is_absolute() or '..' in value.replace('\\','/').split('/'): raise ValueError('模型名称无效')
                for role in ('A','B','mask'):
                    if task[role]:
                        ref=self.store.get('inputs',task[role],pid)
                        if bool(ref.get('mask')) != (role=='mask'): raise ValueError('图片和遮罩类型不匹配')
                if task['mask']:
                    ref=self.store.get('inputs',task['mask'],pid)
                    if ref['provenance'].get('source')!=task['A']: raise ValueError('遮罩属于另一张图片，请重新标注')
                if old and old.get('parent_output'): task['parent_output']=old['parent_output']
                tasks.append(task)
            live={tid for tid,t in previous.items() if not t.get('discarded_at')}
            if len(tasks)>100 or live-seen: raise ValueError('请通过废弃操作移除编辑任务，最多100个')
            if (tasks and data.get('current_task') not in seen) or (not tasks and data.get('current_task') is not None): raise ValueError('当前任务不存在')
            return self.store.plan(pid,dict(name=str(data.get('name') or '图片资产')[:120],revision=data.get('revision'),
                                             current_task=data['current_task'],tasks=tasks))

    def active_task(self,pid,tid):
        task=self.store.get('tasks',tid,pid)
        if task.get('discarded_at'):raise Conflict('编辑任务已废弃，请先从回收站恢复')
        return task

    def discard_task(self,pid,tid,data):
        restore=data.get('restore',False)
        if not isinstance(restore,bool):raise ValueError('恢复标志必须是开关')
        with self.store.lock,self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            p=self.store.project(pid)
            if p['revision']!=data.get('revision'):raise Conflict('项目已更新，请刷新后再整理编辑任务')
            task=self.store.get('tasks',tid,pid)
            if any(r['state'] in ('waiting','submitting','running','unknown') for r in self.store.all('runs',pid)):
                raise Conflict('本项目仍有运行或待确认提交，请先处理完成')
            live=[t for t in self.store.all('tasks',pid) if not t.get('discarded_at')]
            if restore and task.get('discarded_at') and len(live)>=100:raise Conflict('编辑任务已达100个，请先整理其他任务')
            if bool(task.get('discarded_at'))==restore:
                task['discarded_at']=None if restore else time.time()
                self.store.put('tasks',task,db)
                if not restore:
                    for output in self.store.all('outputs',pid):
                        if output['task']==tid and output.get('selected'):
                            output['selected']=False;self.store.put('outputs',output,db)
                    if p['current_task']==tid:
                        index=next(i for i,t in enumerate(live) if t['id']==tid)
                        remaining=[t for t in live if t['id']!=tid]
                        p['current_task']=remaining[min(index,len(remaining)-1)]['id'] if remaining else None
                elif not p.get('current_task'):p['current_task']=tid
                p.update(revision=p['revision']+1,updated=time.time());self.store.put('projects',p,db)
        return self.snapshot(pid)

    def upload(self,pid,file,source=None):
        if source:
            self.store.get('inputs',source,pid)
        return inputs.prepare(self.store,pid,file.stream,file.filename,{'source':source} if source else None,mask=bool(source))

    def library_input(self,pid,data):
        item=self.lib.store.get(data['asset'],data['version'])
        media=next((m for m in item['snapshot']['media'] if m['id']==data.get('media')),None)
        if not media: raise ValueError('请选择这个版本中的图片')
        obj=self.lib.store.object(media['hash'])
        if obj['kind']!='image': raise ValueError('该媒体不是图片，请先使用现有抽帧工具')
        ref=dict(asset=item['id'],version=item['snapshot']['id'],media=media['id'],hash=media['hash'])
        # Idempotent immutable import; no draft is changed until the caller saves.
        record=next((x for x in self.store.all('inputs',pid) if x.get('provenance')==ref),None)
        if not record:
            with self.lib.store.path(obj['path']).open('rb') as stream:
                record=inputs.prepare(self.store,pid,stream,item['snapshot']['name'],ref)
        with self.lib.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO refs VALUES(?,?,?,?,?)',(pid+':'+record['id'],ref['asset'],ref['version'],pid,encode(ref)))
        return record

    def preflight(self,pid,tid):
        self.store.project(pid)
        t=self.active_task(pid,tid); errors=[]; geom=None
        if not t['prompt'].strip(): errors.append('请填写画面描述' if t['submode']=='text' else '请填写编辑指令')
        if t['submode']!='text' and not t.get('A'): errors.append('请选择图片A')
        if t['submode']=='dual' and not t.get('B'):errors.append('请选择图片B')
        if t['submode']=='region':
            if not t.get('mask'):errors.append('请标注需要编辑的区域')
            elif not self.store.get('inputs',t['mask'],pid).get('area'):errors.append('标注范围为空')
        if t['submode']=='text':geom=compiler.geometry('text',0,0,t['settings'])
        elif t.get('A'):
            a=self.store.get('inputs',t['A'],pid)
            geom=compiler.geometry(t['submode'],a['width'],a['height'],t['settings'])
            if t.get('mask'):
                m=self.store.get('inputs',t['mask'],pid)
                if (m['width'],m['height'])!=(a['width'],a['height']):errors.append('遮罩尺寸与原图不符')
        return dict(ready=not errors,errors=errors,geometry=geom,note='输入结构检查；不运行模型。' if t['submode']=='text' else '输入结构检查；不运行模型，区域外可能变化。')

    def select(self,pid,oid):
        self.store.project(pid)
        with self.store.lock,self.store.connect() as db:
            target=self.store.get('outputs',oid,pid)
            self.active_task(pid,target['task'])
            if target.get('removed_at'):raise Conflict('候选已移除，请先从已移除记录中恢复')
            for out in self.store.all('outputs',pid):
                if out['task']==target['task']:
                    out['selected']=out['id']==oid;self.store.put('outputs',out,db)
        return self.snapshot(pid)

    def continue_output(self,pid,oid,revision):
        with self.store.lock:
            p=self.store.project(pid)
            if p['revision']!=revision:raise Conflict('项目已更新，请先保存草稿')
            out=self.store.get('outputs',oid,pid)
            self.active_task(pid,out['task'])
            if out.get('removed_at'):raise Conflict('候选已移除，请先恢复后继续编辑')
            with Path(out['path']).open('rb') as stream:
                ref=inputs.prepare(self.store,pid,stream,'继续编辑',dict(parent_output=oid))
            tid=uid()
            task=dict(id=tid,project=pid,name='继续编辑',submode='single',prompt='',A=ref['id'],B=None,mask=None,
                      settings=copy.deepcopy(compiler.DEFAULTS),models=dict(self.models),parent_output=oid,revision=1)
            with self.store.connect() as db:
                self.store.put('tasks',task,db)
                p.update(current_task=tid,revision=p['revision']+1,updated=time.time());self.store.put('projects',p,db)
        return self.snapshot(pid)

    def ingest(self,pid,oid,data):
        with self.store.lock:
            return self._ingest_visible(pid,oid,data)

    def _ingest_visible(self,pid,oid,data):
        select_output=data.get('select_output',True)
        if not isinstance(select_output,bool):raise ValueError('选用结果必须是开关')
        self.store.project(pid)
        out=self.store.get('outputs',oid,pid);run=self.store.get('runs',out['run'],pid)
        self.active_task(pid,out['task'])
        if out.get('removed_at'):raise Conflict('候选已移除，请先恢复后入库')
        path=Path(out['path']).resolve()
        self.url(pid,path)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=out['hash']: raise ValueError('该候选文件缺失或已变化')
        target=data.get('asset') or None
        version=self.lib.ingest(path,data.get('name') or self.store.project(pid)['name'],
            provenance=dict(type='generated_image',project=pid,task=out['task'],run=run['id'],output=oid,
                            tool=run['snapshot']['submode'],actual_prompt=run['snapshot']['prompt'],
                            records={k:run[k] for k in ('snapshot','seed','source_hash','graph_hash','plugin_version')}),
            key='image-output:'+oid+':'+(target or 'new'),aid=target,revision=data.get('revision'),primary=True)
        def update(o):
            o['library']=dict(asset=version['id'],version=version['version'])
            if select_output:o['selected']=True
        if select_output:self.select(pid,oid)
        self.store.mutate('outputs',oid,update)
        return version
