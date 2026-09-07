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
  request(path,method='GET',body){return api(path,method,body,this.controller.signal);}
  async reload(){
    const p=await this.request('/projects/'+this.project.id);
    if(this.disposed)return;
    if(this.dirty){this.project.runs=p.runs;this.project.outputs=p.outputs;this.project.busy=p.busy;}
    else this.project=p;
    this.emit();
  }
  save(){return singleFlight(this,'pendingSave',async()=>{
    if(!this.dirty)return true;
    this.working=true;
    try {
      const version=this.version, p=this.project, body=structuredClone({revision:p.revision,name:p.name,current_task:p.current_task,tasks:p.tasks});
      const base='/image-projects/'+p.id;
      const plan=await this.request(base+'/change-plan','POST',body);
      const saved=await this.request(base+'/apply','POST',{token:plan.token});
      if(this.disposed)return false;
      if(version===this.version){this.project=saved;this.dirty=false;}
      else {this.project.revision=saved.revision;this.project.runs=saved.runs;this.project.outputs=saved.outputs;}
      return true;
    } finally {this.working=false;}
  });}
  dispose(){this.disposed=true;this.controller.abort();this.listeners.clear();}
}
