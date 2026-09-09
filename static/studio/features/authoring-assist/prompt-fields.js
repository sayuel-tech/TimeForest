import {esc,field,opts} from '../../ui/primitives.js';
import {bindPromptEditor} from '../prompt-library/tools.js';

export const promptFields={prompt:'画面与动作',voice:'人物声音',staging:'人物站位与场景',beats:'整段设计',ending:'末段状态',soundscape:'整体声音',music:'配乐'};
export function profileMarkup(segment,value){
  const kind=segment.dependency?.kind==='upstream_tail'?'tail':'independent';
  const choices=['dance_split','official_image'].flatMap((r,i)=>[[`movie.${kind}.${r}`,(i?'官方工作流':'跳舞 8＋4')+' · 完整正文'],[`movie.${kind}.${r}.structured`,(i?'官方工作流':'跳舞 8＋4')+' · 结构字段']]);
  return field('AI 视频工作流与正文方式',`<select data-authoring-profile>${opts(choices,value.profile_id||choices[0][0])}</select>`,'正文方式属于此工作流配置。模型文件与采样参数在电影制作参数中调整。');
}
export function promptMarkup(value){
  if(value.prompt_mode==='structured')return Object.entries(promptFields).map(([k,title])=>field(title,`<textarea class="director-script" data-prompt-field="${k}">${esc(value.payload?.fields?.[k]||'')}</textarea>`)).join('');
  return field('正式片段 Prompt',`<textarea class="director-script" data-prompt-field="prompt_text">${esc(value.payload?.prompt_text||'')}</textarea>`);
}
export function bindAuthoringPromptTools({ctx,controller,render}){
  ctx.root.querySelectorAll('textarea[data-text],textarea[data-prompt-field]').forEach(el=>{
    const name=el.dataset.promptField||el.dataset.text,purpose=el.dataset.promptField?'video':'script';
    bindPromptEditor(el,{field:'text',fields:['text'],purpose,title:el.closest('label')?.querySelector('span')?.textContent||'创作正文',model:()=>purpose==='video'?'minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors':'',signal:controller.signal,alive:()=>!ctx.session.disposed&&!ctx.session.actionPending&&!ctx.session.working,stamp:()=>JSON.stringify([ctx.selected,ctx.step,ctx.session.project.revision,el.value]),origin:()=>({project:ctx.session.project.id,project_name:ctx.session.project.name,mode:'authoring',target:ctx.selected||'project',scope:name}),collectionScope:name,apply:patch=>{el.value=patch.text;el.dispatchEvent(new Event('input',{bubbles:true}));render();}});
  });
}
