import {esc} from './primitives.js';
import {sourceParametersMarkup} from './source-parameters.js';

const modes={swap:'参考视频换人',image_story:'参考图长视频',text_story:'文生视频',image_assets:'图片资产创作',video_assembly:'视频接续'};
const types={generated:'视频生成',generated_image:'图片生成',derived:'资产派生',local:'本地导入',project:'项目素材',portable_pack:'素材包导入',comfy_output:'目录收集',unknown:'未记录'};
export function projectOriginLink(project){
  if(!project)return '未记录来源项目';
  const label=esc(project.name||project.id);
  if(project.state==='available')return `<a href="${esc(project.url)}">${label}</a>`;
  if(project.state==='removed')return `${label} · 已移除 <a href="#/assets?view=trash&amp;recycle=projects">查看项目回收站</a>`;
  return `${label} · 项目不存在`;
}
export function assetVersionLink(ref,label='查看库内素材与来源'){
  if(!ref?.asset||!ref?.version)return '';
  const query=new URLSearchParams({version:ref.version,...(ref.media?{media:ref.media}:{})});
  return `<a href="#/assets/${encodeURIComponent(ref.asset)}?${esc(query)}">${esc(label)}</a>`;
}
export function lineageMarkup(data){
  if(data?.version!==1)return '<p class="helper">当前后台未提供完整上游追溯，请在保存编辑并结束任务后重启导演台。</p>';
  if(!data.rows?.length)return '';
  const relations={ancestor:'上游素材',derived:'资产派生自',continuation:'视频承接自',image_A:'制作底图 A',image_B:'参考图片 B',image_mask:'局部编辑标注',pack:'外部素材包',reference_image:'参考图片',reference_audio:'参考声音',reference_video:'源视频'};
  const states={pack:'包内身份已映射',historical:'位于历史编排',removed:'已移除或所属任务已废弃',missing:'记录缺失',incomplete:'身份不完整',cycle:'循环记录',limit:'展开上限',unrecorded:'未记录关联',external:'外部身份'};
  return `<details class="asset-lineage"><summary>查看上游派生链 · ${data.rows.length} 项</summary><p class="helper">按制作时记录追溯；参考图与承接底图分开标注。</p><ol>${data.rows.map(r=>`<li><p><strong>${esc(relations[r.relation]||(r.relation?.startsWith('part_')?'合成片段 '+r.relation.slice(5):'上游来源'))}</strong> · ${r.parent?'来自第 '+esc(r.parent)+' 项':'来自当前媒体'}${states[r.state]?' · '+esc(states[r.state]):''}</p>${r.name?`<p>${esc(r.name)}</p>`:''}${r.kind==='asset'&&r.state!=='missing'&&r.state!=='incomplete'?assetVersionLink(r,'查看固定版本'):''}${r.project?`<p>${projectOriginLink(r.project)}</p>`:''}${r.run?`<p class="helper">生成记录 ${esc(r.run)}</p>`:''}${r.output?`<p class="helper">图片结果 ${esc(r.output)}</p>`:''}${r.notice?`<p class="helper">${esc(r.notice)}</p>`:''}${r.parameters?.length?sourceParametersMarkup(r.parameters,{title:'查看此上游制作参数'}):''}</li>`).join('')}</ol>${data.truncated?'<p class="helper">来源较多，已达到本次展开上限；可从固定资产版本继续查看。</p>':''}</details>`;
}
export function assetOriginMarkup(data){
  const rows=data.chain||[];
  return `<section class="asset-origin"><h3>来源与制作记录</h3>${rows.map((r,i)=>`<section><h4>${i?'上游资产 · ':''}${esc(r.name)}</h4>${i?assetVersionLink(r,'查看此固定版本'):''}<dl><dt>来源类型</dt><dd>${esc(types[r.type]||'其他来源')}${r.operation?' · '+esc(r.operation):''}</dd><dt>${i?'上游来源项目':'来源项目'}</dt><dd>${projectOriginLink(r.project)}${r.project?.mode?' · '+esc(modes[r.project.mode]||r.project.mode):''}${r.project?.recorded_name&&r.project.recorded_name!==r.project.name?`<small>制作时项目名：${esc(r.project.recorded_name)}</small>`:''}</dd>${[['task','编辑任务'],['segment','片段'],['run','生成记录'],['previous_run','承接的上一生成记录']].filter(([key])=>r[key]).map(([key,label])=>`<dt>${label}</dt><dd>${esc(r[key])}</dd>`).join('')}</dl></section>`).join('')}${lineageMarkup(data.lineage)}${data.notice?`<p class="helper">${esc(data.notice)}</p>`:''}${data.prompt?`<details><summary>查看制作时提示词</summary><pre>${esc(data.prompt)}</pre></details>`:''}${data.parameters?.length?sourceParametersMarkup(data.parameters,{title:'查看制作时参数'}):'<p class="helper">当前媒体没有可展示的制作参数记录。</p>'}${data.parts?.length?`<details><summary>制作时的合成顺序 · ${data.parts.length} 段</summary><ol>${data.parts.map(p=>`<li>${esc(p.run||'原视频片段')}${p.start!=null&&p.end!=null?' · '+esc(p.start)+'–'+esc(p.end)+' 秒':''}</li>`).join('')}</ol></details>`:''}<p class="helper">来源记录只供查看，不会应用到制作参数。上游记录与当前媒体的制作参数分别保存。</p></section>`;
}
