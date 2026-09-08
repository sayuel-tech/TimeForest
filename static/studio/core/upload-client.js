import {ApiError} from './api-client.js';

/** One request, true wire progress followed by server processing; never auto-retry. */
export function uploadForm(path,body,onProgress=()=>{},signal){
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();let settled=false;
    const abort=()=>xhr.abort();
    const finish=(fn,value)=>{if(settled)return;settled=true;signal?.removeEventListener('abort',abort);onProgress(null);fn(value);};
    xhr.open('POST','/api/v5'+path);xhr.responseType='text';
    xhr.upload.onprogress=e=>{if(!settled)onProgress({phase:'正在上传文件',loaded:e.loaded,total:e.lengthComputable?e.total:null});};
    xhr.upload.onload=()=>{if(!settled)onProgress({phase:'文件已传输，服务器正在处理',loaded:0,total:null});};
    xhr.onload=()=>{
      const raw=xhr.responseText;let data;try{data=JSON.parse(raw);}catch{data=null;}
      if(xhr.status>=200&&xhr.status<300&&data!==null)finish(resolve,data);
      else finish(reject,new ApiError(data?.error||'上传响应无法确认，请先检查素材列表与任务状态。',xhr.status,data?.code,{kind:data?.error_kind||'website',raw:data?.error_raw??raw}));
    };
    xhr.onerror=()=>finish(reject,new ApiError('上传连接中断，处理结果尚未确认；请先检查素材列表与任务状态，勿重复添加。',0,undefined,{kind:'network'}));
    xhr.onabort=()=>finish(reject,new DOMException('上传已取消','AbortError'));
    if(signal?.aborted){finish(reject,new DOMException('上传已取消','AbortError'));return;}
    signal?.addEventListener('abort',abort,{once:true});
    onProgress({phase:'正在上传文件',loaded:0,total:null});xhr.send(body);
  });
}

export function uploadAsset(projectId,file,onProgress,signal){
  const body=new FormData();body.append('file',file);body.append('kind','video');body.append('purpose','source');
  return uploadForm('/projects/'+projectId+'/assets',body,info=>{if(info)onProgress(info);},signal);
}
