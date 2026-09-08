import {promptTools,expandPrompt} from '../../ui/prompt-editor.js';
import {onScopedClose,esc,scopedModal,toast} from '../../ui/primitives.js';
import {chooseAction} from '../../ui/choice-dialog.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {promptApi,promptCatalog} from './api.js';
import {mountPromptBrowser} from './browser.js';
import {openEditor,contentText,fieldNames} from './editor.js';

export async function pickPrompt({purpose,model,signal}){
  const identity=await promptApi('/identify','POST',{purpose,model},signal);
  const catalog=await promptCatalog(signal);
  if(signal?.aborted)return null;
  const branch=catalog.branches.find(b=>b.purpose===purpose&&b.family===identity.family)?.id;
  const d=scopedModal('<div class="dialog-heading"><h2>从提示词库选择</h2><p>先查看再应用；选择不会保存或生成。</p></div><div class="prompt-picker" data-picker></div><div class="dialog-actions"><button data-cancel>取消</button></div>');
  return new Promise(resolve=>{
    let settled=false;const done=v=>{if(settled)return;settled=true;signal?.removeEventListener('abort',abort);d.close();resolve(v);};
    const abort=()=>done(null);signal?.addEventListener('abort',abort,{once:true});d.oncancel=e=>{e.preventDefault();done(null);};d.querySelector('[data-cancel]').onclick=()=>done(null);onScopedClose(d,()=>done(null));
    mountPromptBrowser(d.querySelector('[data-picker]'),{purpose,branch,signal,onChoose:done}).catch(e=>{if(d.open){d.querySelector('[data-picker]').innerHTML=errorFeedback(e);bindErrorFeedback(d);}});
  });
}

/** The adapter owns draft identity and writes; this component owns all shared actions. */
export function bindPromptEditor(el,adapter){
  if(!el||el.dataset.promptTools)return;el.dataset.promptTools='1';
  const tools=promptTools(el,Boolean(adapter.bundle));
  const showSource=()=>{const s=adapter.source?.();tools.querySelector('[data-source]').textContent=s?`${s.record?'基于生成时记录':'基于库版本 '+s.version}${s.text!==el.value?'，已修改':''}`:'';};showSource();el.addEventListener('input',showSource);
  let working=false;
  tools.querySelectorAll('[data-tool]').forEach(button=>button.onclick=async()=>{
    if(working||el.disabled||!el.isConnected||!adapter.alive())return;
    working=true;tools.querySelectorAll('button').forEach(b=>b.disabled=true);
    const stamp=adapter.stamp(),before=el.value,start=el.selectionStart,end=el.selectionEnd;
    const valid=()=>el.isConnected&&adapter.alive()&&adapter.stamp()===stamp&&!el.disabled;
    try{
      const action=button.dataset.tool;
      if(action==='copy'){await navigator.clipboard.writeText(before);toast('已复制');return;}
      if(action==='favorite'||action==='bundle'){
        const existing=await promptApi('/favorite-current','POST',{content:adapter.bundle?.()||{type:'text',text:before},origin:{...adapter.origin(),scope:adapter.collectionScope}},adapter.signal);
        if(!valid())return;
        if(existing.entry){toast('已收藏保存过的创作记录');return;}
        const catalog=await promptCatalog(adapter.signal),identity=await promptApi('/identify','POST',{model:adapter.model(),purpose:adapter.purpose},adapter.signal);
        if(!valid())return;
        await openEditor({catalog,signal:adapter.signal,entry:{title:adapter.title,content:action==='bundle'?adapter.bundle():{type:'text',text:before},purpose:adapter.purpose,branch:catalog.branches.find(b=>b.purpose===adapter.purpose&&b.family===identity.family)?.id||null,favorite:true,source:adapter.origin()}});return;
      }
      if(action==='expand'){
        const value=await expandPrompt(before,adapter.title,adapter.signal);if(value===null)return;
        if(!valid())throw new Error('目标或草稿已变化，请重新打开编辑；未覆盖新内容。');
        adapter.apply({[adapter.field]:value});return;
      }
      const entry=await pickPrompt({purpose:adapter.purpose,model:adapter.model(),signal:adapter.signal});if(!entry)return;
      if(!valid())throw new Error('目标或草稿已变化，请重新选择提示词。');
      let patch;
      if(entry.content.type==='fields'){
        const fields=entry.content.fields;
        const allowed=Object.keys(fields).filter(k=>adapter.fields.includes(k));
        const missing=Object.keys(fields).filter(k=>!adapter.fields.includes(k));
        if(!allowed.length)throw new Error('当前工具不支持此字段组合。可在库内复制所需文字。');
        const d=scopedModal(`<div class="dialog-heading"><h2>选择应用字段</h2><p>仅替换勾选字段，其他内容保留。${missing.length?'不支持：'+esc(missing.map(k=>fieldNames[k]||k).join('、')):''}</p></div>${allowed.map(k=>`<label class="field"><span><input type="checkbox" data-patch="${k}" checked> ${esc(fieldNames[k]||k)}</span><pre class="prompt-text">${esc(fields[k])}</pre></label>`).join('')}${adapter.bundle?`<p>正文方式：${entry.content.prompt_mode==='full'?'完整正文':'按工作流整理结构'}；应用正文时同步此方式。</p>`:''}<div class="dialog-actions"><button data-cancel>取消</button><button data-apply class="primary">应用所选字段</button></div>`);
        patch=await new Promise(resolve=>{let done=false;const finish=v=>{if(done)return;done=true;d.close();resolve(v);};d.oncancel=e=>{e.preventDefault();finish(null);};d.querySelector('[data-cancel]').onclick=()=>finish(null);d.querySelector('[data-apply]').onclick=()=>{const out=Object.fromEntries([...d.querySelectorAll('[data-patch]:checked')].map(el=>[el.dataset.patch,fields[el.dataset.patch]]));if(adapter.bundle&&'prompt' in out)out.prompt_mode=entry.content.prompt_mode;finish(out);};onScopedClose(d,()=>finish(null));});
        if(!patch||!Object.keys(patch).length)return;
      }else{
        const choice=await chooseAction({title:'应用提示词到 '+adapter.title,message:'替换当前文字，或插入打开前的光标/选区位置；只修改草稿。',signal:adapter.signal,choices:[{label:'取消',value:null},{label:'插入选区',value:'insert'},{label:'替换正文',value:'replace',primary:true}]});
        if(!choice)return;
        patch={[adapter.field]:choice==='insert'?before.slice(0,start)+entry.content.text+before.slice(end):entry.content.text};
      }
      if(!valid())throw new Error('目标或草稿已变化，请重新选择；原文字保留。');
      const warnings=await adapter.validate?.(patch)||[];
      if(warnings.length){const yes=await chooseAction({title:'核对提示词引用',message:warnings.join('\n')+'\n保留原文字，不自动更改素材编号。',signal:adapter.signal,choices:[{label:'取消应用',value:false},{label:'保留文字并应用',value:true}]});if(!yes)return;}
      if(!valid())throw new Error('当前草稿已变化，请重新应用。');
      adapter.apply(patch,{entry:entry.id,version:entry.version,text:patch[adapter.field]??'',source:entry.source});showSource();toast('已应用到草稿，尚未保存项目');
    }catch(e){if(adapter.alive()&&e.name!=='AbortError'&&tools.isConnected){let box=tools.querySelector('[data-prompt-error]');if(!box){box=document.createElement('div');box.dataset.promptError='1';tools.append(box);}box.innerHTML=errorFeedback(e);bindErrorFeedback(box);}}
    finally{working=false;if(tools.isConnected)tools.querySelectorAll('button').forEach(b=>b.disabled=false);}
  });
}
