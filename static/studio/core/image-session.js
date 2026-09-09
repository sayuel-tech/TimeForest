import {snapshotChange} from './snapshot-update.js';
import {projectContent,mergeProjectRuntime,acceptProjectRevision} from '../contracts/project-refresh.js';
import {readStamp,currentRead,canReplaceDraft} from './async-state.js';
import {api} from './api-client.js';
import {singleFlight} from './single-flight.js';

export class ImageSession {
  constructor(project) {
    this.project=project; this.dirty=false; this.working=false;this.actionPending=false;
    this.disposed=false;this.controller=new AbortController();this.listeners=new Set();this.version=0;
  }
  on(fn){this.listeners.add(fn);return ()=>this.listeners.delete(fn);}
  emit(){if(!this.disposed)this.listeners.forEach(fn=>fn());}
  edit(){this.dirty=true;this.version++;}
  request(path,method='GET',body){return api(path,method,body,this.controller.signal,this.transferProgress);}
  async reload(){
    const stamp=readStamp(this);
    const p=await this.request('/projects/'+this.project.id);
    if(!currentRead(this,stamp,p))return;
    if(this.dirty){this.project.runs=p.runs;this.project.outputs=p.outputs;this.project.busy=p.busy;}
    else this.project=p;
    this.emit();
  }
  receive(p){
    if(this.disposed||p.id!==this.project.id||Number(p.revision)<Number(this.project.revision))return;
    const change=this.pendingRefresh?'content':snapshotChange(this.project,p,projectContent);
    if(change==='none')return false;
    if(canReplaceDraft(this,this.root)&&change==='content'){this.pendingRefresh=false;this.project=p;this.emit();return true;}
    this.pendingRefresh=change==='content';
    this.project.runs=p.runs;this.project.outputs=p.outputs;
    mergeProjectRuntime(this.project,p);
    if(change==='status'&&canReplaceDraft(this,this.root))acceptProjectRevision(this.project,p);
    return false;
  }
  save(){return singleFlight(this,'pendingSave',async()=>{
    if(!this.dirty)return true;
    this.working=true;
    try {
      // A project save can commit before its independent library registration.
      // Retry that exact token before preparing another revision of the draft.
      if(this.retryApply){
        const retry=this.retryApply,saved=await this.request('/image-projects/'+this.project.id+'/apply','POST',{token:retry.token});
        if(this.disposed)return false;
        this.retryApply=null;
        if(this.version===retry.version){this.project=saved;this.dirty=false;return true;}
        this.project.revision=saved.revision;
      }
      const version=this.version, p=this.project, body=structuredClone({revision:p.revision,name:p.name,current_task:p.current_task,tasks:p.tasks});
      const base='/image-projects/'+p.id;
      const plan=await this.request(base+'/change-plan','POST',body);
      if(this.disposed)return false;
      this.retryApply={token:plan.token,version};
      const saved=await this.request(base+'/apply','POST',{token:plan.token});
      this.retryApply=null;
      if(this.disposed)return false;
      if(version===this.version){this.project=saved;this.dirty=false;}
      else {this.project.revision=saved.revision;this.project.runs=saved.runs;this.project.outputs=saved.outputs;}
      return true;
    } catch(error) {
      // Validation/revision rejection did not commit; do not pin a stale token.
      if([400,404,409].includes(error.status))this.retryApply=null;
      throw error;
    } finally {this.working=false;}
  });}
  dispose(){this.disposed=true;this.controller.abort();this.listeners.clear();}
}
