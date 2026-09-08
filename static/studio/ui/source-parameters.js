import {esc} from './primitives.js';
import {productionGroups,imageProductionGroups} from './production-settings.js';

const values={true:'开启',false:'关闭',random:'随机',fixed:'固定',native:'生成声音',mute:'静音',source:'原视频声音',area:'面积＋比例',custom:'自定义宽高',match:'匹配画布',max:'原参考细节'};
export function sourceParametersMarkup(records, {title="查看原片段制作参数"}={}){
  if(!Array.isArray(records)||!records.some(r=>r.fields?.length))return '';
  return `<details class="source-production-parameters"><summary>${esc(title)}</summary><p class="helper">来自制作时保存的运行记录，仅供对照；未记录字段留空，不会应用到当前制作参数。已关闭或跳过的配置不代表本次执行启用。</p>${records.filter(r=>r.fields?.length).map(r=>`<section><h4>${esc(r.title)}</h4>${Object.entries(r.kind==='image'?imageProductionGroups:productionGroups).map(([group,label])=>{
    const fields=r.fields.filter(f=>f.group===group);
    return fields.length?`<h4>${esc(label)}</h4><dl>${fields.map(f=>`<dt>${esc(f.label)}</dt><dd>${esc(typeof f.value==='boolean'?values[f.value]:values[f.value]||String(f.value))}</dd>`).join('')}</dl>`:'';
  }).join('')}</section>`).join('')}</details>`;
}
