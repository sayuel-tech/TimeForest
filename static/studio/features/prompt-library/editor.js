import {onScopedClose,scopedModal,esc,field,opts,toast} from '../../ui/primitives.js';
import {chooseAction} from '../../ui/choice-dialog.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {promptApi} from './api.js';

let currentEditor=null;
export async function closePromptEditor(){return currentEditor?await currentEditor():true;}

export const contentText=c=>c?.type==='fields'?Object.entries(c.fields).filter(([,v])=>v).map(([k,v])=>`${fieldNames[k]||k}：${v}`).join('\n\n'):c?.text||'';
export const fieldNames={prompt:'正文',staging:'场景与外观',beats:'动作节拍',ending:'结尾',voice:'角色声线',soundscape:'环境与动作声',music:'配乐',speaker_order:'发声顺序',swap_custom_prompt:'换人完整正文'};

export function openEditor({catalog,entry,purpose='video',branch,signal,copy=false}){
  const original=entry,creating=!entry?.id||copy||entry.record_kind==='automatic';
  let currentPurpose=entry?.purpose||purpose;
  const selectedBranch=entry&&'branch' in entry?(entry.branch||''):(branch??currentPurpose+':general');
  const d=scopedModal(`<div class="dialog-heading"><span class="eyebrow">PROMPT LIBRARY</span><h2>${creating?'另存提示词模板':'编辑提示词'}</h2><p>${entry?.record_kind==='automatic'?'创作记录保留；这里编辑并保存为独立模板。':'保存到提示词库，不会修改原项目。'}</p></div><form data-prompt-form><div class="split">${field('用途',`<select name="purpose">${opts(Object.entries(catalog.purposes),currentPurpose)}</select>`)}${field('模型家族','<select name="branch"></select>')}</div>${field('名称',`<input name="title" maxlength="160" required value="${esc(entry?.title||'')}">`)}${field('标签（逗号分隔）',`<input name="tags" value="${esc(entry?.tags?.join(', ')||'')}">`)}${entry?.content?.type==='fields'?Object.entries(entry.content.fields).map(([k,v])=>field(fieldNames[k]||k,`<textarea data-content-field="${k}" rows="3">${esc(v)}</textarea>`)).join(''):field('提示词',`<textarea name="text" rows="12" required>${esc(entry?.content?.text||'')}</textarea>`)}<label><input type="checkbox" name="favorite" ${entry?.favorite?'checked':''}> 收藏</label><div data-error role="alert"></div><div class="dialog-actions"><button type="button" data-cancel>取消</button><button class="primary" type="submit">保存到提示词库</button></div></form>`);
  const form=d.querySelector('form');let dirty=false,busy=false;const requestId=crypto.randomUUID();
  const branches=()=>{form.elements.branch.innerHTML=opts([['','待归类'],...catalog.branches.filter(b=>b.purpose===form.elements.purpose.value&&!b.deleted_at).map(b=>[b.id,b.name])],selectedBranch);};branches();
  form.elements.purpose.onchange=()=>{branches();form.elements.branch.value=form.elements.purpose.value+':general';};
  form.oninput=()=>{dirty=true;};
  return new Promise(resolve=>{
    let settled=false;
    const done=value=>{if(settled)return;settled=true;currentEditor=null;signal?.removeEventListener('abort',abort);d.close();resolve(value);};
    const abort=()=>done(null);signal?.addEventListener('abort',abort,{once:true});
    const cancel=async e=>{e?.preventDefault();if(busy)return false;if(dirty){const choice=await chooseAction({title:'放弃本次编辑？',message:'尚未保存的模板修改会丢弃，项目和库内原版本保留。',signal,choices:[{value:false,label:'继续编辑'},{value:true,label:'放弃修改'}]});if(choice!==true)return false;}done(null);return true;};
    currentEditor=()=>cancel();
    d.oncancel=cancel;d.querySelector('[data-cancel]').onclick=cancel;
    onScopedClose(d,()=>done(null));
    form.onsubmit=async e=>{e.preventDefault();if(busy||!d.open)return;busy=true;form.dataset.operationPending='true';form.querySelectorAll('button,input,textarea,select').forEach(el=>el.disabled=true);
      try{
        const c=entry?.content?.type==='fields'?{...entry.content,fields:Object.fromEntries([...form.querySelectorAll('[data-content-field]')].map(el=>[el.dataset.contentField,el.value]))}:{type:'text',text:form.elements.text.value};
        const saved=await promptApi('/entries'+(creating?'':'/'+entry.id),'POST',{revision:entry?.revision,request_id:requestId,title:form.elements.title.value,purpose:form.elements.purpose.value,branch:form.elements.branch.value||null,tags:form.elements.tags.value.split(/[,，]/).map(s=>s.trim()).filter(Boolean),favorite:form.elements.favorite.checked,content:c,source:creating&&original?.id?{...original.source,entry:original.id,version:original.version}:original?.source||{}},signal);
        if(d.open){dirty=false;done(saved);toast('提示词已保存');}
      }catch(error){if(d.open){const box=d.querySelector('[data-error]');box.innerHTML=errorFeedback(error);bindErrorFeedback(box);}}
      finally{busy=false;delete form.dataset.operationPending;if(d.open)form.querySelectorAll('button,input,textarea,select').forEach(el=>el.disabled=false);}
    };
  });
}

export async function editBranch(catalog,branch,purpose,signal){
  const d=scopedModal(`<div class="dialog-heading"><h2>${branch?'管理模型分支':'新增模型分支'}</h2><p>属于${esc(catalog.purposes[branch?.purpose||purpose])}；分类不会安装模型或改变工作流。</p></div><form>${field('名称',`<input name="name" required maxlength="80" value="${esc(branch?.name||'')}">`)}${field('排序',`<input name="position" type="number" value="${branch?.position??10}">`)}${!branch?field('家族标识（可留空自动创建）','<input name="family" maxlength="80" placeholder="例如 wan">','工作流接入时将核实的家族关系绑定到此标识。'):''}<p class="helper">移除分类会隐藏其中条目，内容保留；恢复分类不会恢复单独移除的提示词。需要保留条目在列表中，可先在详情将它们移动到其他分支。</p><div data-error></div><div class="dialog-actions"><button type="button" data-cancel>取消</button>${branch&&!branch.system?`<button type="button" data-remove>${branch.deleted_at?'恢复分类':'移除分类'}</button>`:''}<button class="primary">保存</button></div></form>`);
  let busy=false,dirty=false;
  d.querySelector('form').dataset.promptForm='1';
  d.querySelector('form').oninput=()=>{dirty=true;};
  if(branch){const count=document.createElement('p');count.className='helper';count.textContent=`此分支含 ${branch.entry_count||0} 条提示词（含已移除）。`;d.querySelector('[data-error]').before(count);}
  return new Promise(resolve=>{let settled=false;const done=r=>{if(settled)return;settled=true;currentEditor=null;signal?.removeEventListener('abort',abort);d.close();resolve(r);};const abort=()=>done(null);signal?.addEventListener('abort',abort,{once:true});const cancel=async e=>{e?.preventDefault();if(busy)return false;if(dirty){const discard=await chooseAction({title:'放弃分类修改？',message:'未保存的名称和排序会丢弃，已有分类保持。',signal,choices:[{label:'继续编辑',value:false},{label:'放弃修改',value:true}]});if(!discard)return false;}done(null);return true;};currentEditor=()=>cancel();d.oncancel=cancel;d.querySelector('[data-cancel]').onclick=cancel;onScopedClose(d,()=>done(null));
    const submit=async removed=>{if(busy)return;busy=true;d.querySelectorAll('button').forEach(b=>b.disabled=true);try{const form=d.querySelector('form');const r=await promptApi('/model-branches'+(branch?'/'+branch.id:''),'POST',{revision:branch?.revision,purpose:branch?.purpose||purpose,name:form.elements.name.value,position:Number(form.elements.position.value),family:form.elements.family?.value,removed},signal);if(d.open)done(r);}catch(e){if(d.open){d.querySelector('[data-error]').innerHTML=errorFeedback(e);bindErrorFeedback(d);}}finally{busy=false;if(d.open)d.querySelectorAll('button').forEach(b=>b.disabled=false);}};
    d.querySelector('form').onsubmit=e=>{e.preventDefault();submit(Boolean(branch?.deleted_at));};
    const remove=d.querySelector('[data-remove]');if(remove)remove.onclick=async()=>{const yes=await chooseAction({title:branch.deleted_at?'恢复分类？':'移除分类？',message:'其中内容保留，可在提示词库回收站查看。',signal,choices:[{value:false,label:'取消'},{value:true,label:'确认'}]});if(yes)submit(!branch.deleted_at);};
  });
}
