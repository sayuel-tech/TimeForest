import {onScopedClose,scopedModal,esc,toast} from '../../ui/primitives.js';
import {chooseAction} from '../../ui/choice-dialog.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {promptApi,promptCatalog} from './api.js';
import {openEditor,contentText} from './editor.js';

export function recordSource(target,field,row){
  target.prompt_sources={...target.prompt_sources,[field]:{record:row.source,text:row.content.text}};
}

export function addRecordButton(anchor,{path,signal,apply,label='查看生成时提示词'}){
  if(!anchor||anchor.parentElement.querySelector('[data-prompt-record-added]'))return;
  const button=document.createElement('button');button.type='button';button.dataset.promptRecordAdded='1';button.textContent=label;anchor.insertAdjacentElement('afterend',button);
  button.onclick=()=>showRecords({path,signal,apply});
}
export async function showRecords({path,signal,apply}){
  const d=scopedModal('<div class="dialog-heading"><h2>生成时提示词</h2><p>读取这次结果保存的记录，原项目后来修改的内容不会替换它。</p></div><div data-records>正在读取…</div><div class="dialog-actions"><button data-close>关闭</button></div>');
  d.querySelector('[data-close]').onclick=()=>d.close();
  try{
    const data=await promptApi(path,'GET',undefined,signal);if(!d.open||signal?.aborted)return;
    d.querySelector('[data-records]').innerHTML=data.items.map((r,i)=>`<section><h3>${esc(r.title)}</h3><pre class="prompt-text">${esc(contentText(r.content))}</pre><div class="row"><button data-copy="${i}">复制</button><button data-collect="${i}">收藏到提示词库</button>${apply?`<button data-apply="${i}">用于当前草稿</button>`:''}</div></section>`).join('')||'<p>这次结果没有可读取的提示词记录，未用当前项目正文补齐。</p>';
    d.querySelectorAll('[data-copy]').forEach(b=>b.onclick=async()=>{try{await navigator.clipboard.writeText(contentText(data.items[Number(b.dataset.copy)].content));toast('已复制');}catch(e){toast('复制失败，请选中正文手动复制');}});
    d.querySelectorAll('[data-collect]').forEach(b=>b.onclick=async()=>{try{const row=data.items[Number(b.dataset.collect)],catalog=await promptCatalog(signal);if(!d.open)return;d.close();await openEditor({catalog,signal,entry:{...row,branch:catalog.branches.find(v=>v.purpose===row.purpose&&v.family===row.source.family)?.id||null,favorite:true}});}catch(e){if(d.open)toast(e.message);}});
    d.querySelectorAll('[data-apply]').forEach(b=>b.onclick=async()=>{const row=data.items[Number(b.dataset.apply)];const yes=await chooseAction({title:'用于当前草稿？',message:'将替换当前目标的生成正文。视频按完整正文应用；素材、工作流、生成结果和其他片段保留。保存项目前不会持久化。',signal,choices:[{value:false,label:'取消'},{value:true,label:'应用到草稿'}]});if(!yes||!d.open)return;try{await apply(row);d.close();toast('已应用到当前草稿，尚未保存');}catch(e){toast(e.message);}});
  }catch(e){if(d.open){d.querySelector('[data-records]').innerHTML=errorFeedback(e);bindErrorFeedback(d);}}
}
