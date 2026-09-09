import {esc,field} from '../../ui/primitives.js';

/** Editable output fields retain the response identity and structural relationships. */
export function structuredOutput(payload){
  if(!payload)return '<p class="helper">请按下方问题补充资料，再发起请求。</p>';
  for(const collection of ['shots','segments'])if(payload[collection])return payload[collection].map((item,index)=>`<section class="writing-output-item"><h4>${esc(item.title||'片段 '+(index+1))}</h4>${item.title!==undefined?field('分镜名称',`<input data-output-path="${collection}.${index}.title" value="${esc(item.title)}">`):''}${field('本项内容',`<textarea class="director-script" data-output-path="${collection}.${index}.text">${esc(item.text)}</textarea>`)}${item.planned_seconds!==undefined?field('计划时长（秒）',`<input type="number" min="1" step=".01" data-output-path="${collection}.${index}.planned_seconds" value="${item.planned_seconds}">`):''}</section>`).join('');
  if(payload.fields)return Object.entries(payload.fields).map(([name,value])=>field(({prompt:'画面与动作',voice:'人物声音',staging:'站位与场景',beats:'整段设计',ending:'末段状态',soundscape:'整体声音',music:'配乐'})[name]||name,`<textarea class="director-script" data-output-path="fields.${esc(name)}">${esc(value)}</textarea>`)).join('');
  if(payload.needs)return payload.needs.map(n=>`<section class="writing-output-item"><h4>${esc(n.name)}</h4><p>${esc(n.description)}</p>${n.source_text?`<blockquote>${esc(n.source_text)}</blockquote>`:''}</section>`).join('');
  return `<div class="creation-prose">${esc(payload.replacement_text||payload.summary_text||JSON.stringify(payload,null,2))}</div>`;
}

export function bindStructuredOutput(box,candidate,saved,onEdit){
  if(!candidate)return;
  let payload=structuredClone(saved||candidate.payload);
  box.querySelectorAll('[data-output-path]').forEach(el=>{
    const path=el.dataset.outputPath.split('.');let target=payload;for(const key of path.slice(0,-1))target=target[key];
    el.value=target[path.at(-1)];el.readOnly=candidate.disposition==='applied';
    el.oninput=()=>{target[path.at(-1)]=el.type==='number'?Number(el.value):el.value;onEdit(structuredClone(payload));};
  });
}
