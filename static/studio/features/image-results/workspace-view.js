import {imageSlots,visibleImageSlots} from '../../core/image-inputs.js';
import {withReturnContext} from '../shot-segment-tree/return-context.js';
import {assetVersionLink} from '../../ui/asset-origin.js';
import {candidateButton,resultActions,collectionActions} from '../../ui/result-view.js';
import {workspaceHeader,workspaceSteps} from '../../ui/workspace-chrome.js';
import {importOptions} from '../../ui/reference-assets.js';
import {workspaceActionGroups} from '../../ui/workspace-actions.js';
import {esc,field,opts} from '../../ui/primitives.js';
import {runTiming,runStatusRow} from '../../ui/run-timing.js';
import {workbench,propertyTabs} from '../../ui/workbench.js';
import {imageParameters} from '../image-settings/index.js';
import {errorFeedback} from '../../ui/error-feedback.js';
import {parameterField} from '../../ui/production-settings.js';
import {recordControl,removedRecords} from '../../ui/candidate-records.js';

export const imageSteps=[['edit','图片与编辑'],['results','生成与挑选'],['use','保存与使用']];
import {TASK_STATES} from '../../core/task-state.js';
export const imageRunStates={...TASK_STATES,running:'生成中',success:'已生成'};
const activeStates=new Set(['waiting','submitting','running','unknown']);

export function chosenOutput(project,task,selection){
  const outputs=project.outputs.filter(o=>o.task===task.id&&!o.removed_at);
  return outputs.find(o=>o.id===selection)||outputs.find(o=>o.selected)||outputs.at(-1);
}
export function generationReason(project,task){
  if(project.busy)return '已有任务正在处理，请等待完成或查看运行状态。';
  if(task.submode!=='text'&&!task.A)return '先在素材页签选择待编辑底图。';
  if(task.submode==='dual'&&!task.B)return '多图编辑还需要一张参考图 B。';
  if(!task.prompt.trim())return task.submode==='text'?'写下画面描述后即可生成。':'写下编辑指令后即可生成。';
  return '';
}
export function taskStatus(project,task){
  const run=project.runs.filter(r=>r.task===task.id&&!r.removed_at).at(-1);
  return run?imageRunStates[run.state]||run.state:'草稿';
}
export function imageActionBar({project,task,page,selection,view}){
  const selected=chosenOutput(project,task,selection), reason=generationReason(project,task);
  let primary='',secondary='',hint='';
  const back=page==='edit'?'':`<button data-page="${page==='results'?'edit':'results'}" class="quiet">返回上一步</button>`;
  if(page==='edit'){
    primary=`<button id="image-generate" class="primary" ${reason?'disabled':''}>生成图片</button>`;
    secondary='<button id="image-check" class="quiet">检查输入</button>';
    hint=reason||'生成时自动保存当前草稿。';
  }else if(page==='results'){
    primary=selected?'<button id="image-select" class="primary">选定并继续 →</button>':'';
    hint=selected?'选定当前候选后，进入保存与使用。':'生成完成后在这里比较和挑选。';
  }else if(!selected){
    hint='请先生成并选定一张图片。';
  }else if(!selected.selected){
    primary='<button id="image-select" class="primary">选定这张图片</button>';
    hint='这张候选尚未选定，选定后可保存为资产。';
  }else if(selected.library){
    primary='<button id="image-send" class="primary">用于视频项目 →</button>';
    hint='图片已入库，可用于视频创作或视频接续的参考素材。';
  }else{
    primary=`<button id="${view.saveTarget==='version'?'image-version':'image-ingest'}" class="primary">${view.saveTarget==='version'?'选择资产并添加版本':'保存为新资产'}</button>`;
    hint=view.saveTarget==='version'?'选择现有资产后确认添加版本，原媒体保留。':'保存后可复用到视频项目。';
  }
  return workspaceActionGroups({support:`${back}<div><span id="image-save-state" role="status">${view.dirty?'有未保存修改':'草稿已保存'}</span><small id="image-action-hint">${hint}</small></div><button id="image-save" class="quiet">保存草稿</button>`,actions:`${secondary}${primary}`});
}

function mediaSlot(role,{task,project}){
  const ref=project.inputs.find(i=>i.id===task[role]);
  return `<section class="image-input"><h3>图 ${role} · ${role==='A'?'待编辑底图':'人物／服装等参考'}</h3>${ref?`<div class="image-source-card"><a href="${esc(ref.url)}" target="_blank" rel="noopener"><img src="${esc(ref.url)}" alt="图${role}：${esc(ref.name)}"></a><div><strong>${esc(ref.name)}</strong><small>${ref.width} × ${ref.height}</small></div></div>${assetVersionLink(ref.provenance)}<button class="quiet danger" ${imageSlots.indexOf(role)>1?'data-drop-image-slot':'data-remove-input'}="${role}">移除当前引用</button>${ref.alpha_flattened?'<p class="helper">透明区域在执行副本中使用白底，原件保留。</p>':''}`:'<p class="helper">尚未选择图片</p>'}${!ref&&imageSlots.indexOf(role)>1?`<button class="quiet" data-drop-image-slot="${role}">移除空位</button>`:''}${importOptions([`<button data-upload-trigger="${role}">${ref?'更换图片':'本地图片'}</button>`,`<button data-library="${role}">从资产库选择</button>`])}<input type="file" accept="image/png,image/jpeg,image/webp,image/bmp,image/tiff" data-upload="${role}" aria-label="上传图${role}" hidden></section>`;
}
function multiReferencePanel(ctx){
  const roles=visibleImageSlots(ctx.task),supported=ctx.catalog.multi_reference_version===1;
  const count=roles.filter(role=>ctx.task[role]).length;
  return `<p class="helper" role="status">已选择 ${count} / 9 张图片；默认两图，可继续添加。</p>${roles.slice(1).map(role=>mediaSlot(role,ctx)).join('')}<button id="image-add-reference" ${roles.length>=9||!supported?'disabled':''}>${roles.length>=9?'已达 9 张上限':'＋ 添加参考图片'}</button>${!supported?'<p class="helper">请重启导演台并刷新页面，加载多图保存接口。</p>':''}<button id="image-swap">交换 A / B</button><p class="helper">图 A 为底图，其他图片提供参考。可在指令中按图 A—I 指定用途；空位不参与生成。</p>`;
}
function projectPanel({project}){
  return {id:'project',label:'项目',html:`${field('项目名称',`<input id="image-project-name" maxlength="120" value="${esc(project.name)}">`)}<p class="helper">名称随当前项目草稿保存。</p>`};
}
function outpaintControls({task,catalog}){
  if(task.submode!=='outpaint')return '';
  const fields=imageParameters(task,catalog).filter(f=>f.scope==='settings'&&['left','right','top','bottom'].includes(f.key));
  return `<details class="image-tool-more image-outpaint-controls"><summary>扩边设置</summary><div><div class="split">${field('目标比例',`<select id="image-target-ratio">${opts([['','精确四边'],...['1:1','2:3','3:2','16:9','9:16'].map(v=>[v,v])],'')}</select>`)}${field('原图锚点',`<select id="image-anchor">${opts([['center','居中'],['left','靠左'],['right','靠右'],['top','靠上'],['bottom','靠下']],'center')}</select>`)}</div><div class="image-pads">${fields.map(f=>parameterField({...f,help:''},task.settings[f.key],{attributes:`data-setting="${esc(f.key)}"`})).join('')}</div><p class="helper">四边像素基于 1 MP 工作图；也可拖动画布边缘调整，原图不变。</p></div></details>`;
}
function inputPanel({task,project}){
  if(task.submode==='text')return `<h3>当前任务输入</h3><p>文生图只使用画面描述，不需要底图。</p><dl class="image-facts"><dt>画面描述</dt><dd id="image-input-prompt">${task.prompt.trim()?'已填写':'尚未填写'}</dd></dl><p class="helper">尺寸与采样参数在右上方制作参数中调整。</p>`;
  return `<h3>当前任务输入</h3><dl class="image-facts">${visibleImageSlots(task).map(role=>`<dt>图${role}</dt><dd>${esc(project.inputs.find(i=>i.id===task[role])?.name||'尚未选择')}</dd>`).join('')}<dt>编辑指令</dt><dd id="image-input-prompt">${task.prompt.trim()?'已填写':'尚未填写'}</dd>${task.submode==='region'?`<dt>标注</dt><dd id="image-input-mask">${task.mask?'已保存标注':'尚未保存标注'}</dd>`:''}</dl><p class="helper">检查会先保存当前草稿；实际运行素材和参数以该次生成记录为准。</p>`;
}
function resultProperties(ctx){
  const {project,task,selection,view,catalog,page}=ctx,chosen=chosenOutput(project,task,selection);
  if(!chosen)return propertyTabs(view,[{id:'result',label:'当前任务',html:`<h3>${esc(task.name)}</h3><p>${esc(catalog.tools[task.submode])}</p><p class="helper">生成后可比较候选、选定并保存到资产库。</p>`},projectPanel(ctx)]);
  const run=project.runs.find(r=>r.id===chosen.run),snapshot=run?.snapshot;
  const facts=`<h3>${chosen.selected?'已选图片':'当前候选'}</h3><dl class="image-facts"><dt>尺寸</dt><dd>${chosen.width} × ${chosen.height}</dd><dt>种子</dt><dd>${esc(run?.seed??'未记录')}</dd><dt>编辑方式</dt><dd>${esc(catalog.tools[snapshot?.submode||task.submode])}</dd><dt>保存状态</dt><dd>${chosen.library?'已入库':'尚未入库'}</dd></dl>`;
  const save=`${facts}${!chosen.library?`${field('资产名称',`<input id="image-asset-name" maxlength="120" value="${esc(view.assetName||task.name)}">`)}${field('保存目标',`<select id="image-save-target">${opts([['new','保存为新资产'],['version','添加到现有资产版本']],view.saveTarget)}</select>`)}<p class="helper">新资产以图片类型保存。添加版本时可选择目标资产，保留已有媒体。</p>`:'<p class="helper">可从下方继续用于视频项目。</p>'}`;
  const sources=`<h3>本次实际输入</h3>${imageSlots.filter(role=>snapshot?.inputs?.[role]).map(role=>{const ref=project.inputs.find(i=>i.id===snapshot[role]);return ref?`<figure class="image-run-source"><img src="${esc(ref.url)}" alt="运行时图${role}"><figcaption>图 ${role} · ${esc(ref.name)}</figcaption></figure>`:'';}).join('')}<p class="image-run-prompt">${esc(snapshot?.prompt||'本次未记录指令')}</p>${snapshot?`<details><summary>原始运行记录</summary><pre>${esc(JSON.stringify(snapshot,null,2))}</pre></details>`:''}`;
  return propertyTabs(view,[{id:'result',label:page==='use'?'保存':'结果',html:page==='use'?save:facts},{id:'sources',label:'来源',html:sources},projectPanel(ctx)]);
}
function editor(ctx){
  const {task:t,presetNames}=ctx;
  const toolbar=`<div class="image-tools" role="group" aria-label="图片编辑方式">${['single','dual','region','outpaint',...(ctx.catalog.text_to_image_version===1?['text']:[])].map(id=>`<button data-tool="${id}" aria-pressed="${t.submode===id}">${esc(ctx.catalog.tools[id])}</button>`).join('')}<button class="quiet inspector-toggle" data-toggle-inspector>${ctx.view.inspectorHidden?'显示属性':'收起属性'}</button></div>`;
  if(t.submode==='text')return `${toolbar}<div class="image-viewport is-empty text-intent"><div class="empty image-editor-empty"><div><h3>用文字描绘一张图片</h3><p>描述主体、场景、构图与风格，然后生成候选。</p><small id="image-dimensions">正在读取输出尺寸…</small></div></div></div><div class="image-prompt"><label for="image-prompt">画面描述</label><textarea id="image-prompt" rows="5" placeholder="例如：清晨森林中的木屋，薄雾与柔和阳光，水彩插画…">${esc(t.prompt)}</textarea></div>`;
  return `${toolbar}
  <div class="image-canvas-tools" role="group" aria-label="画布工具"><div class="image-tool-group"><button data-view="fit">适应</button><button data-view="actual">100%</button><button data-view="minus" aria-label="缩小画布">−</button><button data-view="plus" aria-label="放大画布">＋</button></div><div class="image-tool-group"><button data-pen="pan" aria-pressed="${!['region','outpaint'].includes(t.submode)}">平移</button>${t.submode==='outpaint'?'<button data-pen="expand" aria-pressed="true">扩边</button>':''}${t.submode==='region'?'<button data-pen="brush" aria-pressed="true">画笔</button><button data-pen="erase" aria-pressed="false">擦除</button><label>笔刷 <input id="image-brush" type="number" min="1" max="600" value="40"></label>':''}</div>${outpaintControls(ctx)}${t.submode==='region'?'<div class="image-tool-group"><button data-mask="undo">撤销</button><button data-mask="redo">重做</button><details class="image-tool-more"><summary>标注选项</summary><div><button id="image-mask-visible" aria-pressed="true">隐藏标注</button><button data-mask="clear">清空标注</button></div></details></div>':''}</div>
  <div class="image-viewport ${t.A?'':'is-empty'}" tabindex="0" aria-label="图片编辑画布">${t.A?'<canvas></canvas>':'<div class="empty image-editor-empty"><img src="/static/assets/image-studio/empty-editor.webp" width="150" height="100" alt=""><div><h3>放入一张图，开始新的创作</h3><p>从素材页签选择底图。</p><button id="image-open-assets" class="quiet">选择图片 →</button></div></div>'}</div>
  <div class="image-canvas-caption"><small id="image-dimensions">${t.A?'读取画面尺寸…':'原图保留，编辑结果另存'}</small>${t.submode==='region'?`<small id="image-mask-state" role="status">${t.mask?'已保存标注':'尚未标注'} · 区域外可能变化。</small>`:''}</div>
  <div class="image-prompt"><div class="row between"><label for="image-prompt">编辑指令</label><select id="image-preset" aria-label="选用编辑指令示例"><option value="">选用指令示例…</option>${opts(presetNames[t.submode].map((n,i)=>[i,n]),'')}</select></div><textarea id="image-prompt" rows="3" placeholder="描述需要修改什么、保留什么…">${esc(t.prompt)}</textarea></div>`;
}
export function imageRecordHistory(project,task){
  const runs=project.runs.filter(r=>r.task===task.id);
  const noOutput=runs.filter(r=>!r.removed_at&&!project.outputs.some(o=>o.run===r.id)&&['failed','cancelled'].includes(r.state));
  return (noOutput.length?`<details class="removed-records"><summary>未产生候选的记录（${noOutput.length}）</summary>${noOutput.map(r=>`<div class="candidate-record"><small>${esc(r.id.slice(0,8))} · ${imageRunStates[r.state]} · 种子 ${esc(r.seed??'未记录')}</small><p>${esc(r.note||'')}</p>${recordControl(r,{image:true,busy:project.busy})}</div>`).join('')}</details>`:'')+removedRecords(runs,{busy:project.busy,preview:r=>{const o=project.outputs.find(o=>o.run===r.id);return o?`<img class="removed-candidate-preview" src="${esc(o.url)}" alt="已移除候选">`:'';}});
}
function results(ctx){
  const {project,task,selection,page,catalog}=ctx,allOutputs=project.outputs.filter(o=>o.task===task.id),outputs=allOutputs.filter(o=>!o.removed_at),chosen=chosenOutput(project,task,selection),history=imageRecordHistory(project,task);
  if(!chosen)return history+'<div class="empty image-results-empty"><img src="/static/assets/image-studio/empty-results.webp" width="240" height="160" alt=""><h3>这里将保存每次生成的候选</h3><p>生成后比较、挑选，再保存到资产库。</p></div>';
  const selected=outputs.find(o=>o.selected);
  const identity=`正在查看：候选 ${allOutputs.indexOf(chosen)+1} · ${selected?`已选定：候选 ${allOutputs.indexOf(selected)+1}`:'尚未选定候选'}`;
  return `<p class="helper image-result-context">${identity}</p><div class="image-compare"><img src="${esc(chosen.url)}" alt="${chosen.selected?'已选图片':'当前候选'}" id="image-result-main"></div>${resultActions({inspect:project.runs.find(r=>r.id===chosen.run)?.snapshot?.submode==='text'?'':'<button id="image-compare-toggle" aria-pressed="false">对比原图 A</button>',decide:page==='results'?`<button id="image-reroll" ${generationReason(project,task)?'disabled':''} title="${esc(generationReason(project,task)||'按当前任务原图、指令和参数再生成一个候选')}">重新生成</button>`:'<button id="image-continue">继续编辑</button>',collect:collectionActions({url:chosen.url+'?download=1',media:'图片',filename:'图片资产.png',asset:page==='results'?chosen.library?.asset:null,button:page==='results'?`<button id="image-quick-ingest" ${catalog.quick_ingest_preserves_selection===true?'':'disabled title="当前后台未加载快捷入库，请重启导演台后刷新页面"'}>加入资产库</button>`:''})})}${page==='results'?`<div class="result-candidates" aria-label="生成候选">${outputs.map(o=>{const n=allOutputs.indexOf(o)+1,run=project.runs.find(r=>r.id===o.run);return `<div class="result-candidate">${candidateButton({id:o.id,number:n,viewing:o.id===chosen.id,selected:o.selected,collected:Boolean(o.library),preview:`<img src="${esc(o.url)}" alt="候选 ${n}">`,detail:`${o.width}×${o.height}`,attribute:'data-output'})}${run?recordControl(run,{image:true,selected:o.selected,busy:project.busy}):''}</div>`;}).join('')}</div>`:''}${history}`;
}
export function imageRunClock(run){
  if(run.state==='unknown'||run.closed_without_result)return runTiming({uncertain:true});
  const stamp=value=>Number.isFinite(Number(value))&&Number(value)>0?Number(value):null;
  const created=stamp(run.created),started=stamp(run.started)||stamp(run.progress?.started);
  const live=['waiting','submitting','running'].includes(run.state);
  const end=live?null:stamp(run.finished)||stamp(run.progress?.finished)||stamp(run.updated);
  const start=started||created;
  const waiting=!started&&(run.state==='waiting'||run.state==='cancelled');
  const label=started?'本次任务用时':waiting?(live?'已等待':'等待用时'):'总用时（含等待）';
  return runTiming({start,end,live,label,queuedAt:started?created:null});
}
export function imageRunStatus(project,task){
  const runs=project.runs.filter(r=>r.task===task.id&&!r.removed_at),run=runs.at(-1);
  if(!run)return '';
  const render=r=>`<div class="notice ${r.state==='failed'?'error':''}" role="${r.state==='failed'?'alert':'status'}"><strong>${imageRunStates[r.state]||esc(r.state)}</strong>${r.state==='failed'||r.error_raw?errorFeedback(r):` · ${esc(r.state==='running'?(r.progress?.phase||r.note):r.note)}`}${r.state==='running'&&r.progress?.step_total?` · ${r.progress.step}/${r.progress.step_total}`:''}<small>种子 ${esc(r.seed??'尚未确定')}</small>${r.state==='unknown'?`<button data-reconcile="${r.id}">核对原提交</button>`:''}${r.state==='waiting'?`<button data-cancel="${r.id}">取消等待</button>`:''}</div>`;
  const unresolved=runs.slice(0,-1).filter(r=>activeStates.has(r.state));
  return [...unresolved,run].map(r=>runStatusRow(render(r),imageRunClock(r))).join('');
}
export function renderImageWorkspace(ctx){
  const {project:p,task:t,view,page,catalog}=ctx;
  if(!t)return `${workspaceHeader({name:p.name,code:'IMAGE',modeName:'图片资产创作',summary:'0 个编辑任务'})}<section class="empty"><h2>还没有编辑任务</h2><p>可以新增任务，也可以从回收站恢复已废弃的任务。</p><div class="row"><button id="image-new" class="primary">＋ 新增编辑任务</button><a class="btn quiet" href="#/assets?view=trash&recycle=projects">查看已废弃任务</a></div></section><div id="image-feedback" hidden></div>`;
  const rail=`<div class="row between"><h3>编辑任务</h3><button id="image-new" class="quiet" aria-label="新增编辑任务">＋</button></div><button class="image-task-toggle quiet" aria-expanded="${view.tasksOpen}">当前：${esc(t.name)} · 展开任务</button><div class="image-task-list ${view.tasksOpen?'is-open':''}">${p.tasks.map((x,i)=>`<button class="image-task ${x.id===t.id?'active':''}" data-task="${x.id}" aria-current="${x.id===t.id}"><strong>${String(i+1).padStart(2,'0')} · ${esc(catalog.tools[x.submode])}</strong><span>${esc(x.name)}</span><small>${taskStatus(p,x)}</small></button>`).join('')}<button id="image-task-name" class="quiet">重命名当前任务</button><button id="image-task-discard" class="quiet" ${p.busy||catalog.task_discard_version!==1?'disabled':''} title="${p.busy?'请先处理完成运行或待确认任务':catalog.task_discard_version!==1?'请重启导演台后刷新页面以加载任务废弃功能':'废弃当前任务及其候选，已入库资产保留'}">− 废弃当前任务</button></div>`;
  const handoff=t.authoring_handoff||p.authoring_handoff;
  const scriptHref=handoff?withReturnContext('#/p/'+handoff.script_project_id+'?step='+({intent:0,screenplay:1,asset_screenplay:2,asset_bindings:2,storyboard:3,segment:3,prompt:4,visual_references:4}[handoff.target.layer]??3)+'&target='+(handoff.target.target_ids[0]||''),handoff.return_context):null;
  const back=handoff?`<aside class="notice row between"><span>来自剧本的补图任务。选定结果并加入资产库后，返回剧本核对回填。</span><a href="${esc(scriptHref)}">返回来源剧本</a></aside>`:'';
  const heading=`<div class="shot-heading image-task-heading"><h2>${esc(t.name)}</h2><button class="quiet inspector-toggle" data-toggle-inspector>${view.inspectorHidden?'显示属性':'收起属性'}</button></div>`;
  const properties=page==='edit'&&t.submode==='text'?propertyTabs(view,[{id:'inputs',label:'输入',html:inputPanel(ctx)},projectPanel(ctx)]):page==='edit'?propertyTabs(view,[{id:'assets',label:'素材',html:`${mediaSlot('A',ctx)}${t.submode==='dual'?multiReferencePanel(ctx):''}`},{id:'inputs',label:'输入',html:inputPanel(ctx)},projectPanel(ctx)]):resultProperties(ctx);
  return `${workspaceHeader({name:p.name,code:'IMAGE',modeName:'图片资产创作',stateLabel:taskStatus(p,t),statusId:'image-task-status',titleId:'image-project-title',summary:`${p.tasks.length} 个编辑任务 · ${catalog.tools[t.submode]}`,settings:{id:'image-settings',workflow:catalog.workflow?.name||catalog.workflow_name||catalog.tools[t.submode]||''}})}
  ${workspaceSteps({items:imageSteps.map(([id,name])=>[id,id==='edit'&&t.submode==='text'?'描述与创作':name]),current:page,label:'图片创作工作步骤',attribute:'data-page'})}<div id="image-feedback" role="${view.error?'alert':'status'}" ${view.feedback?'':'hidden'} class="notice ${view.error?'error':''}">${view.error?errorFeedback(view.feedback):esc(view.feedback||'')}</div>
  ${back}${workbench({rail,canvas:(page==='edit'?'':heading)+`<div id="image-run-state">${imageRunStatus(p,t)}</div>`+(page==='edit'?editor(ctx):results(ctx)),inspector:properties,kind:'image-asset-desk'})}
  <footer class="savebar">${imageActionBar(ctx)}</footer>`;
}
