import {enhanceMovieWorkspace} from '../../ui/experience-content.js';
import {assertTimecodeInputs} from '../../ui/timecode-input.js';
import {updateStatusRegion} from '../../ui/status-region.js';
import {creationJobStatus} from '../../ui/creation-job-status.js';
import {snapshotChange} from '../../core/snapshot-update.js';
import {projectContent,mergeProjectRuntime,acceptProjectRevision} from '../../contracts/project-refresh.js';
import {illustratedEmpty,bindDecorativeArt} from '../../ui/empty-state.js';
import {workspaceViewState} from '../../ui/workspace-view-state.js';
import {api} from '../../core/api-client.js';
import {esc,field,opts,toast,scopedModal} from '../../ui/primitives.js';
import {workspaceHeader,workspaceSteps,bindWorkspaceSteps} from '../../ui/workspace-chrome.js';
import {workbench,propertyTabs,bindWorkbench} from '../../ui/workbench.js';
import {readingDisclosure} from '../../ui/prompt-editor.js';
import {workspaceActions} from '../../ui/workspace-actions.js';
import {confirmLeave} from '../../ui/choice-dialog.js';
import {draftStatus} from '../../ui/draft-status.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {mediaPlayer,bindMediaPlayers} from '../../ui/media-player.js';
import {candidateButton,resultActions,collectionActions} from '../../ui/result-view.js';
import {runTiming,runStatusRow} from '../../ui/run-timing.js';
import {referenceAssetCard} from '../../ui/reference-assets.js';
import {sourceParametersMarkup} from '../../ui/source-parameters.js';
import {shotSegmentTree} from '../../features/shot-segment-tree/index.js';
import {createFeature as workflowSettings} from '../../features/workflow-settings/index.js';
import {watchProject} from '../../core/progress-channel.js';
import {canReplaceDraft} from '../../core/async-state.js';
import {withReturnContext} from '../../features/shot-segment-tree/return-context.js';
import {previewEdit} from '../../features/shot-segment-tree/edit-preview.js';
import {recordControl,removedRecords,recordConfirmation} from '../../ui/candidate-records.js';
import {chooseAction} from '../../ui/choice-dialog.js';
import {TASK_STATES} from '../../core/task-state.js';
import {addRecordButton} from '../../features/prompt-library/records.js';

const key=()=>crypto.randomUUID();
export function mountWorkspace(root,initial){
  const controller=new AbortController(),query=new URLSearchParams(location.hash.split('?')[1]||'');
  const session={project:initial,dirty:false,working:false,actionPending:false,disposed:false,controller,request:api,version:0,emit(){}};
  const ctx={root,session,step:Number(query.get('step')||0),selected:query.get('target')||query.get('origin_segment')||initial.content.segment_order[0]||'',viewTake:query.get('take')||query.get('origin_run'),inspectorTab:'source',expanded:new Set(),zoom:Math.min(100,Math.max(8,Number(query.get('zoom'))||30)),selectedItem:query.get('item')||'',generationEdit:null,editDraft:null,timecodeDrafts:new Map(),error:null};
  let saved=structuredClone(initial),catalog=null,sourceView=null;
  const viewState=workspaceViewState(root);
  if(initial.movie_exports?.some(e=>e.export_id===query.get('origin_run')))ctx.step=1;
  const p=()=>session.project,bundle=sid=>[...p().content.source_bundles].reverse().find(b=>b.segment_id===sid),source=sid=>{const b=bundle(sid);return b?p().artifacts[b.snapshot_artifact_id]:null;};
  const edit=()=>ctx.editDraft||p().content.edit,take=tid=>p().movie_takes?.find(t=>t.take_id===tid),url=t=>p().movie_media?.[t?.media?.media_id]?.url;
  async function reload(){saved=await api('/projects/'+p().id,'GET',undefined,controller.signal);session.project=structuredClone(saved);}
  session.receive=next=>{
    const change=snapshotChange(saved,next,projectContent);if(change==='none')return;
    if(canReplaceDraft(session,root)&&change==='content'){saved=structuredClone(next);session.project=next;render();}
    else {
      mergeProjectRuntime(session.project,next);
      const job=p().creation_jobs.filter(j=>j.kind==='media_export'||j.record?.snapshot?.segment_id===ctx.selected).at(-1);
      updateStatusRegion(root.querySelector('[data-creation-status]'),creationJobStatus(job));
      if(change==='status'&&canReplaceDraft(session,root)){saved=structuredClone(next);acceptProjectRevision(session.project,next);}
    }
  };
  const unwatch=watchProject(session,()=>root.querySelectorAll('[data-clock]').forEach(el=>{if(!el.dataset.clockEnd){const t=Math.floor(Date.now()/1000-Number(el.dataset.clock));el.textContent=`${Math.floor(t/60)}分 ${t%60}秒`;}}));
  const unbindPlayers=bindMediaPlayers(root);
  function mark(){session.dirty=true;root.querySelector('[data-draft-status]').textContent=draftStatus(session);}
  async function run(fn){if(session.actionPending)return;session.actionPending=true;ctx.error=null;root.querySelectorAll('button').forEach(b=>b.disabled=true);try{await fn();}catch(error){ctx.error=error;}finally{session.actionPending=false;if(!session.disposed)render();}}
  function draft(){
    if(ctx.generationEdit?.segment_id===ctx.selected)return ctx.generationEdit;
    const b=bundle(ctx.selected),s=source(ctx.selected);if(!b)return null;
    return structuredClone(p().content.generation_drafts.find(d=>d.segment_id===ctx.selected)||{segment_id:ctx.selected,profile_id:b.profile_id,parameter_overrides:{},input_contract_id:s.input_contract.input_contract_id,reference_ids:s.references.map(r=>r.id),upstream_take_id:null,upstream_range:null});
  }
  async function save(){
    assertTimecodeInputs(root,ctx.timecodeDrafts);
    if(session.working)return false;session.working=true;
    root.querySelectorAll('.timecode-display').forEach(input=>input.readOnly=true);
    try{
      const latest=await api('/projects/'+p().id,'GET',undefined,controller.signal);
      if(ctx.generationEdit){const sid=ctx.generationEdit.segment_id,old=saved.content.generation_drafts.find(d=>d.segment_id===sid),now=latest.content.generation_drafts.find(d=>d.segment_id===sid);if(JSON.stringify(old)!==JSON.stringify(now)||JSON.stringify(saved.content.source_bundles)!==JSON.stringify(latest.content.source_bundles))throw Error('片段草稿或来源已被修改。当前输入保留，请核对后再保存。');}
      if(ctx.editDraft&&saved.edit_content_hash!==latest.edit_content_hash)throw Error('时间轴已在其他窗口修改。当前剪辑保留，请先核对。');
      saved=latest;
      if(ctx.generationEdit){await api(`/movie/projects/${p().id}/generation-draft`,'POST',{revision:saved.revision,request_key:key(),...ctx.generationEdit});ctx.generationEdit=null;await reload();}
      if(ctx.editDraft){await api(`/movie/projects/${p().id}/edit/save`,'POST',{revision:saved.revision,request_key:key(),edit_content_hash:saved.edit_content_hash,order:ctx.editDraft.order,item_changes:ctx.editDraft.items.map(i=>({item_id:i.id,range:i.range,included:i.included}))});ctx.editDraft=null;await reload();}
      ctx.timecodeDrafts.clear();session.dirty=false;return true;
    }finally{session.working=false;root.querySelectorAll('.timecode-display').forEach(input=>input.readOnly=false);}
  }
  async function leave(fn){if(session.dirty){const choice=await confirmLeave({save,signal:controller.signal});if(!['save','discard'].includes(choice))return;if(choice==='discard'){ctx.timecodeDrafts.clear();ctx.generationEdit=null;ctx.editDraft=null;session.project=structuredClone(saved);session.dirty=false;}}fn();render();}
  async function command(path,data={}){const result=await api(`/movie/projects/${p().id}/`+path,'POST',{revision:p().revision,request_key:key(),...data});await reload();return result;}
  function currentTake(){const choices=(p().movie_takes||[]).filter(t=>t.movie_segment_id===ctx.selected&&t.state!=='removed');return ctx.viewTake?choices.find(t=>t.take_id===ctx.viewTake):choices.find(t=>t.currently_adopted)||choices.at(-1);}
  async function showSource(t){sourceView=await api(`/movie/projects/${p().id}/takes/${t.take_id}/source`);render();}
  function returnContext(){const item=ctx.step===1?edit().items.find(i=>i.id===ctx.selectedItem):null,sid=item?.movie_segment_id||ctx.selected;return {origin_movie_id:p().id,origin_page:ctx.step===1?'editing':'generation',origin_item_id:item?.id||null,origin_segment_id:sid||null,viewed_take_id:item?.take_id||currentTake()?.take_id||null,script_project_id:p().content.source_project_id,script_target_id:sid||null,source_bundle_id:bundle(sid)?.bundle_id||null,view:{scroll_x:Math.round(root.querySelector('.movie-timeline')?.scrollLeft||0),scroll_y:Math.round(window.scrollY),zoom:ctx.zoom}};}
  function sourceMarkup(s){return `<h3>制作来源</h3>${s?`<a href="#/p/${esc(p().content.source_project_id)}?step=4&target=${esc(ctx.selected)}">回剧本页修改这个片段 →</a><details><summary>当前剧本正文</summary><p class="creation-prose">${esc(s.segment.text||'')}</p></details><p class="helper">修改剧本后回到这里核对同步；已有生成和剪辑保留。</p>`:''}${sourceView?sourceParametersMarkup(sourceView.parameters)+`<details><summary>此候选的实际正文与输入</summary><p class="creation-prose">${esc(sourceView.snapshot?.actual_prompt_text||'未记录')}</p><p>来源包 ${esc(sourceView.bundle?.bundle_id||'未记录')}</p></details>`:''}`;}
  function render(){
    if(session.disposed)return;
    const restoreView=viewState.beforeRender(JSON.stringify([p().id,ctx.step,ctx.selected,ctx.selectedItem,ctx.viewTake]));
    const sources=p().content.segment_order.map(sid=>source(sid)).filter(Boolean),shots=[...new Map(sources.map(s=>[s.shot.ref,s.shot])).values()],segments=sources.map(s=>s.segment),s=source(ctx.selected),t=currentTake();
    let canvas='',rail='',inspector='',support='',actions='';
    const jobs=p().creation_jobs.filter(j=>j.kind==='media_export'||j.record?.snapshot?.segment_id===ctx.selected),job=jobs.at(-1);
    const progress=`<div data-creation-status>${creationJobStatus(job)}</div>`;
    if(ctx.step===0){
      if(!ctx.expanded.size)shots.forEach(s=>ctx.expanded.add(s.ref));
      rail=shotSegmentTree({shots,segments,selected:ctx.selected,expanded:ctx.expanded,fullLabel:'完整剧本目录'});
      const d=draft(),parent=s?.segment.dependency?.upstream_ref,parents=(p().movie_takes||[]).filter(t=>t.movie_segment_id===parent&&t.state==='available');
      const choices=(p().movie_takes||[]).filter(t=>t.movie_segment_id===ctx.selected&&t.state!=='removed');
      canvas=s?`<h2>${esc(s.shot.title||'分镜')} · 生成片段</h2>${readingDisclosure('已保存的正式 Prompt',s.prompt.payload?.prompt_text||Object.values(s.prompt.payload?.fields||{}).join('\n\n')||'尚未完成；可以回剧本页继续创作。')}${parent?`${field('用哪个上游结果续接',`<select data-upstream>${opts([['','请选择'],...parents.map((t,i)=>[t.take_id,`候选 ${i+1} · ${(t.duration_ms/1000).toFixed(2)}秒`])],d.upstream_take_id||'')}</select>`)}${d.upstream_take_id?`<div class="split">${field('上游使用起点（毫秒）',`<input data-upstream-range="in_ms" type="number" min="0" value="${d.upstream_range?.in_ms||0}">`)}${field('上游使用终点（毫秒）',`<input data-upstream-range="out_ms" type="number" min="1" value="${d.upstream_range?.out_ms||0}">`)}</div><p class="helper">此范围只决定生成的片尾输入，与剪辑区间分开保存。</p>`:''}`:''}${progress}<div class="row">${choices.map((c,i)=>candidateButton({id:c.take_id,number:i+1,selected:c.currently_adopted,viewing:c===t,collected:!!c.library_asset,attribute:'data-run-view'})).join('')}</div>${t?mediaPlayer(url(t),'当前候选')+resultActions({inspect:'<button data-take-source>查看制作来源</button>',decide:`<button data-adopt ${t.currently_adopted?'disabled':''}>${t.currently_adopted?'已选用':'选用此结果'}</button>`,collect:collectionActions({url:url(t),asset:t.library_asset,button:'<button data-ingest>加入资产库</button>'})}):illustratedEmpty({image:'/static/assets/movie/empty-takes.webp',title:'等待第一个片段',text:'准备好后生成一个候选。你可以多次生成，再决定选用哪一个。'})}`:`<h2>从剧本组织电影</h2><p>可以导入尚未完成的剧本。回到剧本添加分镜和片段后，点击同步剧本。</p>`;
      inspector=propertyTabs(ctx,[{id:'source',label:'来源',html:sourceMarkup(s)},{id:'references',label:'素材',html:(s?.references||[]).map(r=>referenceAssetCard(r)).join('')||'<p>此片段没有绑定参考素材。</p>'}]);
      support='<button data-sync>同步剧本</button><button data-save>保存草稿</button>';
      actions=`${s?'<button data-preflight>检查工作流</button><button class="primary" data-generate>生成片段</button>':''}<button data-edit-next>下一步 →</button>`;
    }else{
      const value=edit();if(!ctx.selectedItem)ctx.selectedItem=value.order[0]||'';const item=value.items.find(i=>i.id===ctx.selectedItem),selected=take(item?.take_id);
      canvas=`<div class="row"><h2>剪辑拼接</h2><label>时间轴缩放 <input data-zoom type="range" min="8" max="100" value="${ctx.zoom}"></label><button data-edit-updates>处理生成页更新</button></div>${!value.initialized_at?illustratedEmpty({image:'/static/assets/movie/empty-edit.webp',title:'把选好的片段排成作品',text:'按生成页的顺序，将已选用结果放入时间轴。',actions:'<button data-initialize>建立剪辑时间轴</button>'}):`<div class="movie-timeline" role="region" aria-label="横向视频时间轴" tabindex="0"><div class="movie-track" role="list">${value.order.map((id,index)=>{const i=value.items.find(i=>i.id===id),duration=(i.range.out_ms-i.range.in_ms)/1000;return `<button role="listitem" draggable="true" data-item="${id}" aria-pressed="${id===ctx.selectedItem}" class="movie-track-item ${i.included?'':'excluded'}" style="width:${duration*ctx.zoom}px" title="片段 ${index+1} · ${duration.toFixed(2)}秒"><span>${index+1}</span><small>${duration.toFixed(2)}秒</small></button>`;}).join('')}</div></div>${item?`<section class="movie-item-controls"><h3>所选片段 · ${(item.range.out_ms-item.range.in_ms)/1000}秒</h3><div class="row"><button data-move="-1">← 前移</button><button data-move="1">后移 →</button><label class="check"><input data-included type="checkbox" ${item.included?'checked':''}>纳入成片</label></div>${mediaPlayer(url(selected),'剪辑片段')}<div class="split">${field('入点（毫秒）',`<input data-range="in_ms" type="number" min="0" value="${item.range.in_ms}"><button data-playhead="in_ms">使用当前播放位置</button>`)}${field('出点（毫秒）',`<input data-range="out_ms" type="number" min="1" value="${item.range.out_ms}"><button data-playhead="out_ms">使用当前播放位置</button>`)}</div><h3>这个片段的生成关系</h3>${(p().edit_seams||[]).filter(s=>s.item_id===item.id).map(s=>`<p class="notice">${esc(s.message)}</p>`).join('')}<div class="row"><button data-return-generation>回生成页重新生成</button><a class="btn quiet" href="#/p/${esc(p().content.source_project_id)}?step=4&target=${esc(item.movie_segment_id)}">回剧本页修改 Prompt</a><a class="btn quiet" href="#/p/${esc(p().content.source_project_id)}?step=3&target=${esc(source(item.movie_segment_id)?.shot.ref||'')}">回剧本页修改分镜</a><button data-item-source>查看本片段制作记录</button></div>${sourceView?sourceParametersMarkup(sourceView.parameters)+`<details><summary>此候选的实际正文与输入</summary><p class="creation-prose">${esc(sourceView.snapshot?.actual_prompt_text||'未记录')}</p><p>来源包 ${esc(sourceView.bundle?.bundle_id||'未记录')}</p></details>`:''}</section>`:''}`}${progress}${(p().movie_exports||[]).map(e=>`<details data-view-key="export:${esc(e.export_id)}"><summary>已导出成片 · ${(e.duration_ms/1000).toFixed(2)}秒</summary>${mediaPlayer(url(e),'成片')}${collectionActions({url:url(e),asset:e.library_asset,button:`<button data-ingest-export="${e.export_id}">加入资产库</button>`})}</details>`).join('')}`;
      support='<button data-back>返回生成页</button><button data-save>保存剪辑</button>';actions='<button class="primary" data-export>拼接导出</button>';
    }
    root.className='page project-page movie-page';
    root.innerHTML=workspaceHeader({name:p().name,code:'FILM',modeName:'电影创作',stateLabel:TASK_STATES[job?.state]||'草稿',summary:p().content.segment_order.length+' 个剧本片段',settings:ctx.step===0?{id:'movie-settings',workflow:'当前片段参数'}:null})+workspaceSteps({items:[['0','片段生成'],['1','剪辑拼接']],current:String(ctx.step),label:'电影创作步骤'})+(ctx.error?errorFeedback(ctx.error):'')+workbench({rail,canvas,inspector,kind:ctx.step===1?'movie-edit-desk':'movie-generation-desk'})+workspaceActions({support:support+`<span data-draft-status>${draftStatus(session)}</span>`,actions});
    bindWorkspaceSteps(root);bindWorkbench(ctx);bindDecorativeArt(root);bindErrorFeedback(root);
    if(ctx.viewTake&&!t&&ctx.step===0){const notice=document.createElement('aside');notice.className='notice';notice.textContent='指定来源候选已移除或不存在；未替换为最新结果。可以在已移除记录或资产库回收站查看。';root.querySelector('.steps').after(notice);}
    const record=ctx.step===1?take(edit().items.find(i=>i.id===ctx.selectedItem)?.take_id):t;
    if(record)addRecordButton(root.querySelector(ctx.step===1?'[data-item-source]':'[data-take-source]'),{path:`/records/${p().id}?run=${record.take_id}`,signal:controller.signal});
    if(ctx.step===0&&s){const canvas=root.querySelector('.desk-canvas'),records=(p().movie_takes||[]).filter(t=>t.movie_segment_id===ctx.selected).map(t=>({...t,id:t.take_id,state:'complete'}));if(t)canvas.insertAdjacentHTML('beforeend',recordControl({id:t.take_id,state:'complete'},{selected:t.currently_adopted,busy:p().busy}));canvas.insertAdjacentHTML('beforeend',removedRecords(records));root.querySelectorAll('[data-record-remove],[data-record-restore]').forEach(b=>b.onclick=()=>run(async()=>{const restore=!!b.dataset.recordRestore,yes=await chooseAction({title:restore?'恢复候选':'移除候选',message:recordConfirmation(restore),signal:controller.signal,choices:[{value:false,label:'取消'},{value:true,label:restore?'恢复':'移除',primary:true}]});if(!yes)return;await save();await api(`/projects/${p().id}/records/visibility`,'POST',{record:b.dataset.recordRestore||b.dataset.recordRemove,revision:p().revision,removed:!restore});await reload();}));}
    root.querySelectorAll(`a[href^="#/p/${p().content.source_project_id}?"]`).forEach(a=>{a.onclick=()=>{a.href=withReturnContext(a.getAttribute('href'),returnContext());};});
    const timeline=root.querySelector('.movie-timeline');if(timeline&&query.has('scroll_x')){timeline.scrollLeft=Number(query.get('scroll_x'))||0;query.delete('scroll_x');}
    const previewAnchor=root.querySelector('[data-edit-updates]');if(previewAnchor){const button=document.createElement('button');button.textContent='连续预览';button.dataset.previewEdit='';previewAnchor.before(button);button.onclick=()=>run(()=>{const v=edit(),items=v.order.map(id=>v.items.find(i=>i.id===id)).filter(i=>i.included);for(const i of items)if(i.range.in_ms<0||i.range.out_ms<=i.range.in_ms||i.range.out_ms>take(i.take_id).duration_ms)throw Error('请先修正片段的剪辑区间');previewEdit(items,i=>url(take(i.take_id)),controller.signal);});}
    const on=(selector,fn)=>root.querySelectorAll(selector).forEach(b=>b.onclick=fn);
    on('[data-tab]',e=>leave(()=>ctx.step=Number(e.currentTarget.dataset.tab)));on('[data-back]',()=>leave(()=>ctx.step=0));on('[data-edit-next]',()=>leave(()=>ctx.step=1));on('[data-save]',()=>run(async()=>{await save();toast('草稿已保存');}));
    on('[data-select]',e=>leave(()=>{ctx.selected=e.currentTarget.dataset.select;ctx.viewTake=null;sourceView=null;}));on('[data-expand]',e=>{ctx.expanded.has(e.currentTarget.dataset.expand)?ctx.expanded.delete(e.currentTarget.dataset.expand):ctx.expanded.add(e.currentTarget.dataset.expand);render();});
    on('[data-run-view]',e=>{ctx.viewTake=e.currentTarget.dataset.runView;sourceView=null;render();});on('#movie-settings',()=>run(openSettings));
    on('[data-preflight]',()=>run(async()=>{await save();const pf=await command('preflight',{segment_id:ctx.selected});if(!pf.ready)throw Error(pf.issues.join('；'));toast('保存参数与输入检查通过；没有调用生成引擎');}));
    on('[data-generate]',()=>run(async()=>{await save();const pf=await command('preflight',{segment_id:ctx.selected});if(!pf.ready)throw Error(pf.issues.join('；'));const ready=await command('prepare',{segment_id:ctx.selected,source_bundle_id:pf.source_bundle_id,generation_draft_hash:pf.generation_draft_hash});await command('generate',{prepared_request_id:ready.prepared_request_id,prepared_hash:ready.prepared_hash});}));
    on('[data-adopt]',()=>run(async()=>{await save();await command('adopt',{segment_id:ctx.selected,take_id:t.take_id});toast('已选用；已有剪辑可在处理更新中决定是否替换');}));on('[data-take-source]',()=>run(()=>showSource(t)));on('[data-ingest]',()=>run(()=>command('ingest',{result_id:t.take_id,asset_title:p().name+' · 片段'})));on('[data-ingest-export]',e=>run(()=>command('ingest',{result_id:e.currentTarget.dataset.ingestExport,asset_title:p().name+' · 成片'})));
    root.querySelector('[data-upstream]')?.addEventListener('change',e=>{ctx.generationEdit=draft();ctx.generationEdit.upstream_take_id=e.target.value||null;const t=take(e.target.value);ctx.generationEdit.upstream_range=t?{in_ms:0,out_ms:t.duration_ms}:null;mark();render();});root.querySelectorAll('[data-upstream-range]').forEach(el=>el.oninput=()=>{ctx.generationEdit=draft();ctx.generationEdit.upstream_range[el.dataset.upstreamRange]=Number(el.value);mark();});
    on('[data-initialize]',()=>run(()=>command('edit/initialize',{expected_uninitialized:true})));on('[data-item]',e=>{ctx.selectedItem=e.currentTarget.dataset.item;sourceView=null;render();});
    const ensureEdit=()=>ctx.editDraft||=structuredClone(p().content.edit);
    on('[data-move]',e=>{const v=ensureEdit(),index=v.order.indexOf(ctx.selectedItem),target=index+Number(e.currentTarget.dataset.move);if(target<0||target>=v.order.length)return;[v.order[index],v.order[target]]=[v.order[target],v.order[index]];mark();render();});
    root.querySelectorAll('[data-item]').forEach(b=>{b.ondragstart=e=>e.dataTransfer.setData('text/plain',b.dataset.item);b.ondragover=e=>e.preventDefault();b.ondrop=e=>{e.preventDefault();const id=e.dataTransfer.getData('text/plain'),v=ensureEdit();if(!v.order.includes(id)||id===b.dataset.item)return;v.order.splice(v.order.indexOf(id),1);v.order.splice(v.order.indexOf(b.dataset.item),0,id);mark();render();};});
    root.querySelector('[data-zoom]')?.addEventListener('input',e=>{ctx.zoom=Number(e.target.value);root.querySelectorAll('[data-item]').forEach(b=>{const i=edit().items.find(i=>i.id===b.dataset.item);b.style.width=(i.range.out_ms-i.range.in_ms)/1000*ctx.zoom+'px';});});
    function changeRange(k,value){ensureEdit().items.find(i=>i.id===ctx.selectedItem).range[k]=value;mark();}
    root.querySelectorAll('[data-range]').forEach(el=>el.oninput=()=>changeRange(el.dataset.range,Number(el.value)));on('[data-playhead]',e=>{ctx.timecodeDrafts.delete('edit:'+ctx.selectedItem+':edit:'+e.currentTarget.dataset.playhead);changeRange(e.currentTarget.dataset.playhead,Math.round((root.querySelector('.media-player video')?.currentTime||0)*1000));render();});root.querySelector('[data-included]')?.addEventListener('change',e=>{ensureEdit().items.find(i=>i.id===ctx.selectedItem).included=e.target.checked;mark();render();});
    on('[data-return-generation]',()=>leave(()=>{ctx.selected=edit().items.find(i=>i.id===ctx.selectedItem).movie_segment_id;ctx.step=0;}));on('[data-item-source]',()=>run(()=>showSource(take(edit().items.find(i=>i.id===ctx.selectedItem).take_id))));on('[data-sync]',()=>run(sync));on('[data-edit-updates]',()=>run(updates));on('[data-export]',()=>run(exportMovie));
    enhanceMovieWorkspace({ctx,project:p(),edit:edit(),mediaURL:url,currentTake:t,source,mark});
    restoreView();unbindPlayers.refresh();
  }
  async function openSettings(){
    if(!source(ctx.selected))throw Error('请先选择一个生成片段');catalog=await api('/movie/catalog');const d=draft(),profile=catalog.profiles.find(x=>x.profile_id===d.profile_id),recipe=catalog.recipes.find(r=>r.id===profile.recipe),projection={mode:'image_story',settings:{...structuredClone(recipe.defaults),...d.parameter_overrides}};
    workflowSettings({project:projection,catalog,settingsScope:'当前电影片段草稿',session,api:()=>api('/movie/catalog'),setDirty(){ctx.generationEdit={...d,profile_id:`movie.${source(ctx.selected).segment.dependency?.kind==='upstream_tail'?'tail':'independent'}.${projection.settings.recipe}${d.profile_id.endsWith('.structured')?'.structured':''}`,parameter_overrides:structuredClone(projection.settings)};mark();},persistDraft:save,renderProject:render}).openSettings();
  }
  async function review(title,html,buttons){return new Promise(resolve=>{const d=scopedModal(`<h2>${esc(title)}</h2>${html}<div class="dialog-actions"><button data-cancel>取消</button>${buttons}</div>`);let done=false;const finish=value=>{if(done)return;done=true;d.close();resolve(value);};d.oncancel=e=>{e.preventDefault();finish(null);};d.querySelector('[data-cancel]').onclick=()=>finish(null);d.querySelector('[data-apply]').onclick=()=>finish(d);controller.signal.addEventListener('abort',()=>finish(null),{once:true});});}
  async function sync(){await save();const source=await api('/authoring/projects/'+p().content.source_project_id),plan=await command('sync/preview',{source_project_id:source.id,source_revision:source.revision,target_segment_ids:[]});if(!plan.changes.length){toast('来源剧本尚无片段');return;}const d=await review('核对剧本同步',`<p>同步所选片段的正文、Prompt 与资产绑定；已有候选、选用和剪辑保持。</p>${plan.changes.map(c=>`<label class="check"><input data-sync-id="${c.change_id}" type="checkbox" checked>${esc(c.label)}</label>`).join('')}`,'<button class="primary" data-apply>同步所选</button>');if(d)await command('sync/apply',{plan_id:plan.plan_id,plan_hash:plan.plan_hash,selected_change_ids:[...d.querySelectorAll('[data-sync-id]:checked')].map(e=>e.dataset.syncId)});}
  async function updates(){await save();const plan=await command('edit/updates',{edit_content_hash:p().edit_content_hash});if(!plan.changes.length){toast('没有待处理的生成更新');return;}const d=await review('处理生成页更新',plan.changes.map(c=>field(c.label,`<select data-change="${c.change_id}">${opts(c.item_id?[['keep','保留剪辑结果'],['replace','替换为新选用'],['exclude','排除这个片段']]:[['add','添加到时间轴末尾'],['exclude','添加但不纳入成片']],c.item_id?'keep':'add')}</select>`)).join(''),'<button class="primary" data-apply>应用这些决定</button>');if(d)await command('edit/updates/apply',{plan_id:plan.plan_id,plan_hash:plan.plan_hash,decisions:[...d.querySelectorAll('[data-change]')].map(e=>({change_id:e.dataset.change,action:e.value,insert_after_item_id:null,new_range:null}))});}
  async function exportMovie(){await save();const d=await review('拼接导出',`<p>按当前时间轴顺序导出纳入的片段，保留原声音；无声音片段补静音。</p><div class="split">${field('宽',`<input data-width type="number" value="${ctx.exportDraft?.width||1920}" min="16" step="2">`)}${field('高',`<input data-height type="number" value="${ctx.exportDraft?.height||1080}" min="16" step="2">`)}</div>${field('画幅处理','<select data-fit><option value="contain">完整保留画面</option><option value="cover">裁切填满画面</option></select>')}`,'<button class="primary" data-apply>检查并导出</button>');if(!d)return;ctx.exportDraft={width:Number(d.querySelector('[data-width]').value),height:Number(d.querySelector('[data-height]').value),fps_num:24,fps_den:1,fit:d.querySelector('[data-fit]').value,audio_policy:'preserve_or_silence',container:'mp4'};const pf=await command('export/preflight',{edit_content_hash:p().edit_content_hash,output:ctx.exportDraft});if(!pf.ready)throw Error(pf.issues.join('；'));if(pf.partial&&!await review('仅导出已完成部分','<p>部分剧本片段尚未纳入时间轴。本次只导出当前已选片段。</p>','<button class="primary" data-apply>确认部分导出</button>'))return;if(pf.seam_warnings?.length&&!await review('核对片段接点',pf.seam_warnings.map(s=>'<p>'+esc(s.message)+'</p>').join(''),'<button class="primary" data-apply>保留这些接点并导出</button>'))return;await command('exports',{accepted_seams:(pf.seam_warnings||[]).map(s=>s.id),preflight_id:pf.preflight_id,preflight_hash:pf.input_hash,confirmed_partial_export:!!pf.partial});}
  render();return {session,saveBeforeLeave:save,ctx,render,dispose(){session.disposed=true;unwatch();unbindPlayers();viewState.dispose();controller.abort();}};
}
