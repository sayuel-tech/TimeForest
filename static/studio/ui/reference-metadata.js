import {esc,field,opts,scopedModal} from './primitives.js';

export const referencePurposes=kind=>kind==='audio'?[['voice','音色参考']]:[['character','角色'],['face','脸部'],['costume','服装'],['scene','场景'],['palette','色系'],['prop','道具']];
export const needsSubject=purpose=>['character','face','costume','voice'].includes(purpose);
export function referenceMetadata(kind,purpose,subject){
  if(!referencePurposes(kind).some(([value])=>value===purpose))throw new Error('素材用途与类型不匹配');
  if(needsSubject(purpose)&&!/^([1-9]|[1-9][0-9])$/.test(String(subject)))throw new Error('角色编号须为1～99');
  return {purpose,subject:needsSubject(purpose)?String(subject):''};
}

/** Collect intent only. Import, draft mutation and persistence belong to the caller. */
export function chooseReferenceMetadata({kind='image',initial={},media=[],signal,title='确认素材用途',applyLabel='确认添加'}={}){
  if(signal?.aborted)return Promise.resolve(null);
  return new Promise(resolve=>{
    const selected=media.find(m=>m.role==='primary')||media[0];
    const d=scopedModal(`<h2>${esc(title)}</h2>${media.length?field('素材文件',`<select data-reference-media>${opts(media.map(m=>[m.id,m.name||m.meta.kind]),selected.id)}</select>`):''}${field('素材用途','<select data-reference-purpose></select>')}${field('角色编号',`<input data-reference-subject type="number" min="1" max="99" step="1" value="${esc(initial.subject??'1')}">`,'同一角色使用相同编号；场景、色系和道具不需要角色编号。')}<p class="helper">确认后用于当前片段；资料 PROMPT 不会加入创作正文。取消不会添加或修改素材。</p><p data-reference-error role="alert"></p><div class="dialog-actions"><button data-reference-cancel>取消</button><button class="primary" data-reference-apply>${esc(applyLabel)}</button></div>`);
    let done=false;
    const finish=value=>{if(done)return;done=true;signal?.removeEventListener('abort',abort);d.removeEventListener('close',closed);d.close();resolve(value);};
    const abort=()=>finish(null),closed=()=>{if(!d.open)finish(null);};
    signal?.addEventListener('abort',abort,{once:true});d.addEventListener('close',closed);
    d.oncancel=event=>{event.preventDefault();finish(null);};
    const purpose=d.querySelector('[data-reference-purpose]'),subject=d.querySelector('[data-reference-subject]'),file=d.querySelector('[data-reference-media]');
    const currentKind=()=>file?media.find(m=>m.id===file.value).meta.kind:kind;
    const syncSubject=()=>{subject.disabled=!needsSubject(purpose.value);};
    const syncKind=()=>{const values=referencePurposes(currentKind());purpose.innerHTML=opts(values,values.some(([v])=>v===initial.purpose)?initial.purpose:values[0][0]);syncSubject();};
    syncKind();purpose.onchange=syncSubject;if(file)file.onchange=syncKind;
    d.querySelector('[data-reference-cancel]').onclick=()=>finish(null);
    d.querySelector('[data-reference-apply]').onclick=()=>{
      try{const value=referenceMetadata(currentKind(),purpose.value,subject.value);finish({...value,...(file?{media:file.value}:{})});}
      catch(error){d.querySelector('[data-reference-error]').textContent=error.message;}
    };
  });
}
