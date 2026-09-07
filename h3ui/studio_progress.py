"""Observe ComfyUI events without submitting or modifying a workflow."""
import json,threading,time,uuid
from pathlib import Path
from urllib.parse import quote


def read(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');tmp.replace(path)


def local_progress(root,phase,**details):
    path=Path(root)/'live-progress.json';data=read(path)
    data.update(phase=phase,updated=time.time(),step=None,step_total=None,**details)
    try:write(path,data)
    except OSError:pass


def workflow_summary(directory):
    d=Path(directory);g=read(d/'workflow.json');m=read(d/'manifest.json')
    if not g:return None
    def inputs(n):return g.get(str(n),{}).get('inputs',{})
    two='214' in g
    split=inputs(289).get('step')
    total=inputs(14).get('steps')
    size=m.get('compiled',{}).get('geometry',{});qa=read(d/'qa.json')
    return dict(model=inputs(1).get('unet_name'),two_pass=two,
        width=size.get('width',inputs(20).get('width')),height=size.get('height',inputs(20).get('height')),
        output_width=qa.get('width',size.get('output_width')),output_height=qa.get('height',size.get('output_height')),
        steps=split if split is not None else inputs(14).get('steps',inputs(8).get('steps')),total_steps=total,split_core=split is not None,
        sampler=inputs(13).get('sampler_name',inputs(8).get('sampler_name')),
        denoise=inputs(14).get('denoise'),scale=inputs(215).get('mode.scale',inputs(51).get('scale_by')),
        refine_steps=total-split if split is not None else inputs(222).get('steps',inputs(9).get('refine_steps')),
        refine_denoise=inputs(222).get('denoise'),
        workflow=str(d/'workflow.json'),audio_source='第二采' if inputs(23).get('samples')==['214',1] else '第一采',checkpoint_source='第二采' if inputs(393).get('latent')==['214',1] else '第一采',
        picture_source='第二采' if two else '第一采')


class ProgressWatch:
    def __init__(self,url,client_id,graph,directory,root,shot,task=0,task_total=1):
        self.url=url.replace('https://','wss://',1).replace('http://','ws://',1)+'/ws?clientId='+quote(client_id)
        self.graph=graph;self.directory=Path(directory);self.root=Path(root)
        self.lock=threading.RLock();self.stop=threading.Event();self.socket=None;self.thread=None
        self.done=set();self.last_write=0
        self.data=dict(started=time.time(),updated=time.time(),phase='连接生成服务',shot=shot,task=task,
                       task_total=task_total,connected=False,node=None,step=None,step_total=None,
                       nodes_done=0,nodes_total=len(graph),prompt_id=None,finished=None)
    def publish(self,force=True,**values):
        with self.lock:
            self.data.update(values,updated=time.time(),nodes_done=len(self.done))
            if not force and time.monotonic()-self.last_write<.5:return
            self.last_write=time.monotonic()
            # Telemetry failure must never interrupt model execution.
            try:
                write(self.directory/'progress.json',self.data)
                write(self.root/'live-progress.json',self.data)
            except OSError:pass
    def phase(self,node):
        if '289' in self.graph:
            split=self.graph['289']['inputs']['step'];total=self.graph['14']['inputs']['steps']
            if node=='16':return f'第一采：原日程前{split}步，低分辨率生成'
            if node=='214':return f'第二采：原日程剩余{total-split}步，放大后细化'
            if node in ['394','395','396']:return '保存二采无损尾部与声音'
        if node in ['16','50']:return '第一采：低分辨率生成'
        if node in ['215','51','53']:return '潜空间放大与二采准备'
        if node=='214':return '第二采：补充画面细节'
        if node in ['17','23']:return '解码画面与声音'
        if node in ['18','19','393']:return '保存视频与续接检查点'
        ct=self.graph.get(node,{}).get('class_type','')
        if 'Loader' in ct or ct in ['LoadImage','LoadAudio','LoadVideo']:return '加载模型与参考素材'
        if node in ['20','52','105']:return '准备提示词与音视频条件'
        return '准备工作流条件'
    def event(self,message):
        kind=message.get('type');data=message.get('data') or {}
        with self.lock:
            expected=self.data.get('prompt_id')
            if expected and data.get('prompt_id') and str(data['prompt_id'])!=expected:return
            if kind=='status':return
            if kind=='execution_start':self.publish(phase='工作流开始执行',prompt_id=data.get('prompt_id'));return
            if kind=='execution_cached':
                self.done.update(str(n) for n in data.get('nodes',[]));self.publish();return
            if kind in ['executing','progress']:
                node=str(data.get('node') or self.data.get('node') or '')
                if kind=='executing' and not data.get('node'):
                    self.publish(phase='生成完成，等待本地处理',step=None,step_total=None);return
                if node!=self.data.get('node'):
                    if self.data.get('node'):self.done.add(self.data['node'])
                    self.data.update(node=node,phase=self.phase(node),node_type=self.graph.get(node,{}).get('class_type',''),step=None,step_total=None)
                if kind=='progress':
                    self.publish(False,step=data.get('value'),step_total=data.get('max'),last_event=time.time())
                else:self.publish(last_event=time.time())
            elif kind in ['execution_error','execution_interrupted']:
                self.publish(phase='生成中断，请查看错误',finished=time.time(),error=data.get('exception_message') or kind)
            elif kind=='execution_success':
                if self.data.get('node'):self.done.add(self.data['node'])
                self.publish(phase='生成完成，等待本地处理',step=None,step_total=None,last_event=time.time())
    def start(self):
        self.publish()
        try:
            import websocket
            self.socket=websocket.create_connection(self.url,timeout=2,suppress_origin=True)
            self.publish(connected=True,phase='等待提交与排队')
        except Exception as e:self.publish(phase='实时进度连接暂不可用；仍会等待生成结果',connection_error=str(e))
        self.thread=threading.Thread(target=self.listen,daemon=True);self.thread.start()
        return self
    def listen(self):
        import websocket
        while not self.stop.is_set():
            if self.socket is None:
                if self.stop.wait(3):break
                try:
                    self.socket=websocket.create_connection(self.url,timeout=2,suppress_origin=True)
                    self.publish(connected=True,connection_error=None)
                except Exception:continue
            try:
                value=self.socket.recv()
                if not value:raise ConnectionError('closed')
                if isinstance(value,str):self.event(json.loads(value))
            except websocket.WebSocketTimeoutException:continue
            except Exception:
                if not self.stop.is_set():self.publish(connected=False,connection_error='实时通道已断开，正在重连；节点进度可能不是最新')
                try:self.socket.close()
                except Exception:pass
                self.socket=None
    def submitted(self,prompt_id):self.publish(prompt_id=prompt_id)
    def close(self):
        self.stop.set()
        if self.socket:
            try:self.socket.close()
            except Exception:pass
        if self.thread:self.thread.join(timeout=2.5)


def snapshot_runtime(p,root):
    runtime=read(Path(root)/'live-progress.json')
    active=p.get('status') in ['generating','assembling','preparing'] or bool(p.get('busy') and (p.get('current_job') or {}).get('project_id')==p['id'])
    # Source preparation can replace all segments; old telemetry remains historical.
    attempts=[a for s in p['segments'] for a in s.get('attempts',[])]
    if not active and not attempts and not p.get('export'):runtime={}
    if not active and runtime.get('prompt_id'):
        runs=[r for a in attempts for t in a.get('tasks',[]) for r in t.get('attempts',[])] + attempts
        if not any(r.get('prompt_id')==runtime['prompt_id'] for r in runs):runtime={}
    runtime['active']=active
    for s in p['segments']:
        a=next((x for x in s['attempts'] if x['id']==s.get('selected')),None)
        if s['status'] in ['generating','interrupted'] and s['attempts']:a=s['attempts'][-1]
        if not a:continue
        runs=[]
        for task in a.get('tasks',[]):
            if task['attempts']:runs.append(task['attempts'][-1])
        if not a.get('tasks'):runs=[a]
        s['execution_info']=dict(started=a.get('created'),finished=a.get('completed'),status=a['status'],
            completed_tasks=a.get('completed_tasks'),task_total=len(a.get('tasks',[])) or 1,
            runs=[dict(id=r['id'],prompt_id=r.get('prompt_id'),seed=r.get('seed'),directory=r['directory'],
                       summary=workflow_summary(r['directory']),progress=read(Path(r['directory'])/'progress.json')) for r in runs])
    return runtime
