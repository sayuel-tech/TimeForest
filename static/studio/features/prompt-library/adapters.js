import {bindPromptEditor} from './tools.js';
import {api} from '../../core/api-client.js';
import {promptApi} from './api.js';
const fields=['prompt','staging','beats','ending','voice','soundscape','music','speaker_order'];
const origin=(p,t,scope)=>({project:p.id,project_name:p.name,mode:p.mode,target:t.id||'project',scope});
function base(session,p,t,field,title,purpose,model,changed,render){
  return {field,title,purpose,fields:[field],model:()=>model,signal:session.controller.signal,
    alive:()=>!session.disposed&&!session.working&&!session.actionPending,
    stamp:()=>JSON.stringify([session.version,session.project.revision,t,model]),
    origin:()=>({...origin(p,t,field),model}),collectionScope:field,source:()=>t.prompt_sources?.[field],
    apply:(patch,source)=>{Object.assign(t,patch);if(source){t.prompt_sources={...t.prompt_sources};for(const key of Object.keys(patch)){if(key==='prompt_mode')continue;t.prompt_sources[key]={entry:source.entry,version:source.version,text:patch[key]};}}changed();render();}
  };
}
export function bindVideoPrompts(ctx){
  const p=ctx.project;
  ctx.root.querySelectorAll('textarea[data-field][data-segment]').forEach(el=>{
    const field=el.dataset.field;if(![...fields,'swap_custom_prompt'].includes(field))return;
    const t=p.segments.find(s=>s.id===el.dataset.segment);if(!t)return;
    const a=base(ctx.session,p,t,field,`P${t.index+1} · ${el.closest('label')?.querySelector('span')?.textContent||field}`,'video',p.settings.model,ctx.setDirty,ctx.renderEdit);
    if(p.mode!=='swap'){
      a.fields=fields;a.bundle=()=>({type:'fields',fields:Object.fromEntries(fields.map(k=>[k,t[k]||''])),prompt_mode:t.prompt_mode||'structured'});
      a.collectionScope='segment';
    }
    a.validate=async patch=>{
      const draft={...t,...patch};
      const inv=await api(`/projects/${p.id}/input-preview`,'POST',{segment:t.id,segments:p.segments.map(s=>s.id===t.id?draft:s),settings:p.settings},a.signal);
      const check=await promptApi('/check-tags','POST',{text:Object.values(patch).join('\n'),rows:inv.inputs,segment:draft,recipe:p.settings.recipe},a.signal);
      return [...(inv.warnings||[]),...check.warnings];
    };
    bindPromptEditor(el,a);
  });
  const el=ctx.root.querySelector('#swap-project-custom');
  if(el){const target=p.swap_prompt;const a=base(ctx.session,p,target,'custom','项目默认换人正文','video',p.settings.model,ctx.setDirty,ctx.renderEdit);a.collectionScope='swap_custom_prompt';a.source=()=>p.prompt_sources?.custom;a.apply=(patch,source)=>{target.custom=patch.custom;if(source)p.prompt_sources={...p.prompt_sources,custom:{entry:source.entry,version:source.version,text:patch.custom}};ctx.setDirty();ctx.renderEdit();};bindPromptEditor(el,a);}
}
export function bindImagePrompts({root,session,task,changed,render}){
  if(!task)return;
  const a=base(session,session.project,task,'prompt',task.name+' · 编辑指令','image',task.models?.unet,changed,render);
  a.collectionScope=task.submode;
  bindPromptEditor(root.querySelector('#image-prompt'),a);
}
export function bindAssemblyPrompts({root,session,extension,changed,render}){
  if(!extension)return;
  const p=session.project,e=extension,a=base(session,p,e,'prompt','当前续写段 · 后续画面与声音','video',e.configurations[e.recipe]?.model,changed,render);
  a.collectionScope='extension';
  a.validate=async patch=>(await promptApi('/check-assembly/'+p.id,'POST',{extension:e.id,references:e.references,text:patch.prompt},a.signal)).warnings;
  bindPromptEditor(root.querySelector('[data-prompt]'),a);
}
