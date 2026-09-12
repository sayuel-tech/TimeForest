import {seedFields} from '../../ui/production-settings.js';
import {importOptions} from '../../ui/reference-assets.js';
import {esc,field,opts,fmt,status} from '../../ui/primitives.js';
import {propertyTabs} from '../../ui/workbench.js';
import {inputActions} from '../../ui/input-inventory.js';

const control=(s,key,label,help='')=>field(label,`<textarea class="short" data-field="${key}" data-segment="${s.id}">${esc(s[key]||'')}</textarea>`,help);

export function assetCommands(ctx,s) {
  const swap=ctx.project.mode==='swap';
  return importOptions([`<label class="upload">${swap?'选择角色图':'本地图片'}<input type="file" accept="image/png,image/jpeg,image/webp" ${swap?'':'multiple'} data-upload="image" data-segment="${s.id}"></label><label class="upload">本地声音<input type="file" accept="audio/*" multiple data-upload="audio" data-segment="${s.id}"></label>${ctx.catalog.asset_library_version?`<button type="button" data-library-use="${s.id}">从资产库选择</button>`:''}${s.index?`<button type="button" class="quiet" data-inherit="${s.id}">从P1沿用指定素材</button>`:''}`]);}

export function shotProperties(ctx,s) {
  const assets=ctx.localAssets(s),swap=ctx.project.mode==='swap';
  const assetHTML=`${ctx.assetModeControl(s)}<p class="helper">${ctx.assetModeLabel(s)} · ${assets.length}份</p>${assetCommands(ctx,s)}<div class="asset-grid compact-assets">${assets.map(a=>ctx.assetCard(a,s)).join('')||'<p class="helper">尚无参考素材。连续段可以仅承接上一段声画。</p>'}</div><p class="helper">资料PROMPT仅供存档，不会自动加入本段正文。</p>`;
  const soundHTML=`<p class="helper">参考声音只提供音色与说话方式，不复制录音台词。</p>${field('本段发声顺序',`<input data-field="speaker_order" data-segment="${s.id}" value="${esc(s.speaker_order||'')}" placeholder="例如 2,1">`,'按实际先后写角色ID；2,1表示角色2是S1，角色1是S2。无对白可留空。文戏兼容配方沿用原映射。')}${control(s,'voice','角色声线')}${control(s,'soundscape','环境与动作声')}${control(s,'music','配乐（留空为无配乐）')}`;
  const advanced=`${s.index&&!swap?field('与上一段的关系',`<select aria-label="P${s.index+1}场景边界" data-field="boundary" data-segment="${s.id}">${opts([['continue','连续承接'],['new_scene','新场景']],s.boundary)}</select>`,'只有新场景独立开始；素材继承与续接分开控制。'):''}${seedFields({mode:s.seed_mode,value:s.seed,lastSeed:s.last_seed,modeAttributes:`data-field="seed_mode" data-segment="${esc(s.id)}"`,valueAttributes:`data-field="seed" data-segment="${esc(s.id)}"`})}${!swap?field('正文方式',`<select data-field="prompt_mode" data-segment="${s.id}">${opts([['structured','按工作流整理结构'],['full','完整H3正文']],s.prompt_mode)}</select>`)+control(s,'staging','场景与站位')+control(s,'beats','视觉节拍')+control(s,'ending','结束状态'):''}`;
  const inputs=`${inputActions(ctx,s)}<p class="helper">核对当前草稿的素材编号与职责。保存预检显示已保存编排；实际运行文件记录当次固定输入。</p><details><summary>内部渲染安排</summary>${s.task_plan?s.task_plan.map((t,i)=>`<p>任务${i+1}：渲染${fmt(t.raw/24)}秒，交付${fmt(t.deliver/24)}秒</p>`).join(''):`<p>渲染${s.raw}帧 · 重复头${s.head}帧 · 尾裁${s.tail}帧</p>`}</details>`;
  return propertyTabs(ctx,[{id:'assets',label:'素材',html:assetHTML},{id:'sound',label:'声音',html:soundHTML},{id:'advanced',label:'设置',html:advanced},{id:'inputs',label:'输入',html:inputs}]);
}

export function shotHeading(ctx,s) {
  return `<div class="shot-heading"><div><span class="eyebrow">P${String(s.index+1).padStart(2,'0')}</span><h2>${fmt((s.requested_frames??s.deliver)/24)}秒片段</h2></div><span class="helper">预计 ${fmt(s.deliver/24)}秒</span>${status(s.status)}<button type="button" class="quiet inspector-toggle" data-toggle-inspector>${ctx.inspectorHidden?'显示属性':'收起属性'}</button></div>`;
}

export function shotPrompt(ctx,s) {
  // HTML removes the first newline after <textarea>; provide a sentinel so draft whitespace survives.
  return ctx.project.mode==='swap'?ctx.swapPromptEditor(s):field(ctx.project.mode==='text_story'?'这一段发生什么？':'本段镜头与表演',`<textarea class="director-script ${ctx.project.mode==='text_story'?'writing-script':''}" data-field="prompt" data-segment="${s.id}" aria-label="P${s.index+1}提示词" placeholder="按顺序写下镜头、动作与原文台词……">\n${esc(s.prompt)}</textarea>`,'每15秒或不足15秒，为一个片段填写提示词。实际有效片长可略短；不会多出需要填写的提示词。');
}
