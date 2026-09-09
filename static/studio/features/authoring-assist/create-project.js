import {api} from '../../core/api-client.js';
import {scopedModal,field,esc} from '../../ui/primitives.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';

export async function createCreationProject(mode,go){
  const dialog=scopedModal(`<div class="dialog-heading"><span class="eyebrow">${mode.code} · NEW PRODUCTION</span><h2>${mode.name}</h2><p>${mode.description}</p></div><form data-create-form>${field('项目名称','<input name="title" required maxlength="120" autofocus>')}${mode.id==='movie'?field('来源剧本','<select name="source" required disabled><option>正在读取剧本…</option></select>','可以选择尚未完成的剧本，先制作已经准备好的片段。'):''}<div data-create-error></div><div class="dialog-actions"><button type="button" data-cancel>取消</button><button class="primary" type="submit">开始创作 →</button></div></form>`);
  let busy=false;const key=crypto.randomUUID(),sources=new Map();
  dialog.oncancel=e=>{if(busy)e.preventDefault();};dialog.querySelector('[data-cancel]').onclick=()=>{if(!busy)dialog.close();};
  if(mode.id==='movie'){
    try{const data=await api('/projects');if(!dialog.open)return;const select=dialog.querySelector('[name=source]');
      data.projects.filter(p=>p.mode==='authoring').forEach(p=>sources.set(p.id,p));
      select.innerHTML='<option value="">选择剧本项目</option>'+[...sources.values()].map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');select.disabled=false;
      if(!sources.size){dialog.querySelector('[data-create-error]').innerHTML='<p>还没有剧本项目。请先进入剧本创作，可以只写好一部分。</p>';dialog.querySelector('[type=submit]').disabled=true;}
    }catch(error){dialog.querySelector('[data-create-error]').innerHTML=errorFeedback(error);bindErrorFeedback(dialog);}
  }
  dialog.querySelector('form').onsubmit=async e=>{
    e.preventDefault();if(busy)return;busy=true;
    const controls=[...dialog.querySelectorAll('button,input,select')];controls.forEach(el=>el.disabled=true);
    try{
      const body={request_key:key,title:e.target.elements.title.value};
      if(mode.id==='movie'){const source=sources.get(e.target.elements.source.value);if(!source)throw Error('请选择来源剧本');Object.assign(body,{source_project_id:source.id,source_revision:source.revision,segment_ids:[]});}
      const p=await api('/'+mode.id+'/projects','POST',body);dialog.close();go('/p/'+p.id);
    }catch(error){dialog.querySelector('[data-create-error]').innerHTML=errorFeedback(error);bindErrorFeedback(dialog);}
    finally{busy=false;controls.forEach(el=>el.disabled=false);}
  };
}
