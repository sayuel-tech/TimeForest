import {snapshotChange} from '../../core/snapshot-update.js';
import {projectContent,mergeProjectRuntime,acceptProjectRevision} from '../../contracts/project-refresh.js';
import {workspaceViewState} from '../../ui/workspace-view-state.js';
import {updateStatusRegion} from '../../ui/status-region.js';
import {addRecordButton,recordSource} from '../../features/prompt-library/records.js';
import {promptCollectionNotice} from '../../features/prompt-library/collection.js';
import {bindAssemblyPrompts} from '../../features/prompt-library/adapters.js';
import {sourceTarget} from '../../core/source-target.js';
import {showSourceNavigation} from '../../ui/source-navigation.js';
import {assetVersionLink} from '../../ui/asset-origin.js';
import {canReplaceDraft,uncertainMutation,requireKnownStatus} from '../../core/async-state.js';
import {asyncFeedback} from '../../ui/async-feedback.js';
import {TASK_STATES} from '../../core/task-state.js';
import {mediaPlayer,bindMediaPlayers} from '../../ui/media-player.js';
import {candidateButton,resultActions as resultActionBar,collectionActions} from '../../ui/result-view.js';
import {recordControl,removedRecords,recordConfirmation} from '../../ui/candidate-records.js';
import {draftStatus} from '../../ui/draft-status.js';
import {chooseVideoImport} from './import-dialog.js';
import {sourceParametersMarkup} from './source-parameters.js';
import {trackItems,moveTrack} from './track.js';
import {workspaceActions} from '../../ui/workspace-actions.js';
import {importOptions} from '../../ui/reference-assets.js';
import {referencePanels,bindReferences} from './references.js';
import {api} from '../../core/api-client.js';
import {watchProject} from '../../core/progress-channel.js';
import * as ui from '../../ui/primitives.js';
import {workbench,propertyTabs,bindWorkbench} from '../../ui/workbench.js';
import {workspaceHeader,workspaceSteps,bindWorkspaceSteps} from '../../ui/workspace-chrome.js';
import {runTiming,runStatusRow} from '../../ui/run-timing.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {pickLibraryAsset} from '../../features/asset-picker/index.js';
import {settingsDialog} from './settings.js';

const ACTIVE=new Set(['preparing','submitting','running','unknown']);
const labels={...TASK_STATES,running:'生成中'};
export const activeClips=p=>p.assembly.clips.filter(c=>!c.removed_at);
export function savePayload(p){return {...(p.assembly_track_version===1?{track_order:trackItems(p).map(row=>row.key)}:{}),revision:p.revision,draft_revision:p.assembly.draft_revision,name:p.name,output:p.assembly.output,clips:activeClips(p).map(c=>({...c,extensions:c.extensions.filter(e=>!e.removed_at)}))};}
export function moveClip(p,id,offset){
  const clips=activeClips(p),index=clips.findIndex(c=>c.id===id),to=index+offset;
  if(index<0||to<0||to>=clips.length)return p;
  const [moved]=clips.splice(index,1);clips.splice(to,0,moved);
  return {...p,assembly:{...p.assembly,clips:[...clips,...p.assembly.clips.filter(c=>c.removed_at)]}};
}

export function mountWorkspace(root,project,catalog){
  if(project.assembly_contract_version!==1||catalog.assembly_contract_version!==1)throw new Error('视频接续后台尚未更新，请重启导演台后刷新。');
  if(project.assembly_track_version!==1||catalog.assembly_track_version!==1)throw new Error('当前后台尚未加载视频轨道，请在任务结束后重启导演台并刷新。');
  const session={project:structuredClone(project),version:0,dirty:false,working:false,disposed:false};
  let step=0,clipId=activeClips(project)[0]?.id,extensionId=null,viewRun=null,error=null,polling=false,dialogBusy=false,pendingRefresh=false;
  const viewState=workspaceViewState(root);
  const disposePlayers=bindMediaPlayers(root);
  const controller=new AbortController();const ctx={root,inspectorTab:'import',inspectorHidden:false};
  const sourceLocation=sourceTarget(project);
  if(sourceLocation?.state==='found'){step=sourceLocation.step;clipId=sourceLocation.clip||clipId;extensionId=sourceLocation.extension||null;viewRun=sourceLocation.run;ctx.inspectorTab='source';}
  session.controller=controller;session.root=root;
  const asyncStatus=asyncFeedback(root,controller.signal);session.connection=asyncStatus.connection;
  const p=()=>session.project,clips=()=>activeClips(p()),clip=()=>clips().find(c=>c.id===clipId)||clips()[0];
  const extension=()=>clip()?.extensions.find(e=>e.id===extensionId&&!e.removed_at);
  const duration=e=>p().assembly.runs.find(r=>r.id===e.selected)?.report?.duration??e.seconds;
  const busy=()=>session.working||p().busy||p().assembly.runs.some(r=>ACTIVE.has(r.state));
  const setDirty=()=>{session.version++;session.dirty=true;const note=root.querySelector('[data-save-state]');if(note)note.textContent=draftStatus(session);};
  const call=(path,body)=>api('/assembly/'+p().id+'/'+path,'POST',body,controller.signal,asyncStatus.transfer);
  const refresh=async()=>{const next=await api('/projects/'+p().id,'GET',undefined,controller.signal);if(!session.disposed){session.awaitingStatus=false;asyncStatus.connection(null);session.project=next;session.dirty=false;}};
  const save=async()=>{if(session.dirty){const next=await call('save',savePayload(p()));if(!session.disposed){session.project=next;session.dirty=false;}}};
  const action=async fn=>{
    if(session.working||session.disposed)return;
    session.working=true;error=null;render();
    try{await fn();}catch(err){if(err.name!=='AbortError'){error=err;if(!session.dirty&&!session.disposed){try{await refresh();}catch{ /* Keep the original operation error. */ }}}}
    finally{session.working=false;if(!session.disposed)render();}
  };
  const mutate=(path,body)=>action(async()=>{requireKnownStatus(session);await save();try{session.project=await call(path,{revision:p().revision,...body});}catch(error){uncertainMutation(session,error);throw error;}});
  async function remove(kind,id){
    if(!await ui.confirm('移除这项内容？','保留原文件和已入库资产，可在资产库回收站恢复；关联续写需要重新选用。','移除'))return;
    await mutate('visibility',{kind,id,removed:true});
  }
  const selectImportedClip=()=>{clipId=clips().at(-1)?.id;extensionId=null;viewRun=null;if(step!==0)ctx.inspectorTab='source';};
  const importFiles=files=>{
    if(!files.length||session.disposed)return;
    return action(async()=>{await save();for(const file of files){const form=new FormData();form.append('revision',p().revision);form.append('file',file);session.project=await call('import',form);}selectImportedClip();});
  };
  async function importLibrary(){
    const items=await pickLibraryAsset({signal:controller.signal,kind:'video',title:'选择要添加的视频',multiple:true});
    if(!items?.length||session.disposed)return;
    await action(async()=>{await save();for(const item of items){const videos=item.snapshot.media.filter(m=>m.meta.kind==='video');const selected=videos.find(m=>m.role==='primary')||videos[0];if(!selected)throw new Error('资产版本中没有视频');session.project=await call('import',{revision:p().revision,reference:{asset:item.id,version:item.snapshot.id,media:selected.id}});}selectImportedClip();});
  }
  async function addVideos(showChoices){
    if(dialogBusy||busy()||session.disposed)return;
    dialogBusy=true;
    try{
      const choice=showChoices?await chooseVideoImport({signal:controller.signal}):{library:true};
      if(!choice||session.disposed)return;
      if(choice.files)await importFiles(choice.files);else await importLibrary();
    }catch(err){if(!session.disposed){error=err;render();}}finally{dialogBusy=false;}
  }
  function player(url,id='assembly-player'){return url?mediaPlayer(url,'当前视频','',{id,className:'assembly-player'}):'<div class="empty"><h3>从视频末尾，继续你的故事。</h3><p>描述后续内容，生成并挑选满意的续接。</p></div>';}
  function runView(r){
    if(!r)return '';
    return `<div data-assembly-run-state="${ui.esc(r.id)}">`+runStatusRow(`<div class="status-message"><strong>${labels[r.state]||ui.esc(r.state)}</strong><p>${ui.esc(r.note||'')}</p>${r.seed!==null?`<small>种子 ${ui.esc(r.seed)}</small>`:''}</div>`,runTiming({start:r.started,end:r.finished,live:ACTIVE.has(r.state)&&r.state!=='unknown',uncertain:r.state==='unknown'}))+
      (r.error?errorFeedback({message:r.error,kind:r.error_kind||'website'}):'')+(ACTIVE.has(r.state)?`<div class="row">${(r.state==='unknown'?['recover','close']:['stop']).map(a=>`<button data-control="${a}" data-run="${r.id}">${{recover:'查询恢复',close:'结束等待',stop:'停止任务'}[a]}</button>`).join('')}</div>`:'')+'</div>';
  }
  function render(){
    const restoreView=viewState.beforeRender(JSON.stringify([p().id,step,clipId,extensionId,viewRun]));
    if(session.disposed)return;
    const c=clip(),e=extension(),locked=busy(),disabled=locked?'disabled':'',draftDisabled=session.working?'disabled':'';
    clipId=c?.id;
    const track=trackItems(p()),selectedKey=e?.selected?'extension:'+e.id:'clip:'+c?.id;
    const selectedItem=track.find(row=>row.key===selectedKey);
    const allRuns=p().assembly.runs.filter(r=>r.kind!=='import'&&(step===2?r.kind==='export':r.extension===e?.id));
    const runs=allRuns.filter(r=>!r.removed_at);
    const candidates=(current)=>`<div class="result-candidates" aria-label="${step===2?'成片':'续接'}候选">${runs.map(v=>`<div class="result-candidate">${candidateButton({id:v.id,number:allRuns.indexOf(v)+1,label:step===2?'成片':'候选',state:labels[v.state],viewing:current?.id===v.id,selected:e?.selected===v.id,collected:Boolean(v.asset),attribute:'data-run-view'})}${recordControl(v,{selected:e?.selected===v.id,busy:locked,assembly:true})}</div>`).join('')}</div>${removedRecords(allRuns,{busy:locked,assembly:true})}`;
    const r=runs.find(r=>r.id===viewRun)||runs.at(-1);
    root.className='page project-page mode-video-assembly';
    const header=workspaceHeader({name:p().name,code:'JOIN',modeName:'视频接续',state:p().status,summary:`${track.length} 个轨道片段 · 原片保留，按需AI续接`,settings:{workflow:e?catalog.recipes.find(v=>v.id===e.recipe)?.name:'本地视频拼接'}});
    const nav=workspaceSteps({items:['视频与排序','续接与挑选','成片'].map((name,i)=>[i,name]),current:step,label:'视频接续工作步骤',attribute:'data-step'});
    const rail=`<div class="row between"><h3>视频目录</h3><button data-open-import title="添加视频" aria-label="添加视频" ${disabled}>＋</button></div><p class="helper">按此顺序拼接 · 选用续接后追加片段</p>${track.map((item,i)=>`<div class="assembly-rail-item" draggable="${!locked}" data-drag="${item.key}"><button class="${item.key===selectedKey?'active':''}" data-track="${item.key}"><small>${String(i+1).padStart(2,'0')} · ${ui.fmt(item.seconds)}秒 · ${item.extension?'已选续接':'原视频'}</small>${item.cover?`<img class="assembly-thumb" src="${ui.esc(item.cover)}" alt="">`:item.url?`<video class="assembly-thumb" src="${ui.esc(item.url)}#t=0.1" preload="metadata" muted playsinline aria-hidden="true"></video>`:''}<strong>${ui.esc(item.name)}</strong></button>${item.key===selectedKey?`<div class="row"><button data-move="-1" aria-label="上移当前视频" ${locked||i===0?'disabled':''}>↑</button><button data-move="1" aria-label="下移当前视频" ${locked||i===track.length-1?'disabled':''}>↓</button><button class="text-link" data-remove-track ${disabled}>移除</button></div>`:''}</div>`).join('')}<p><a href="#/assets?view=trash&recycle=projects">回收站</a></p>`;
    const sourcePanel=c?`<h3>${selectedItem?.extension?'原视频来源':'当前视频'}</h3><p>${ui.esc(c.name)}</p><dl><dt>尺寸</dt><dd>${c.meta.width} × ${c.meta.height}</dd><dt>帧率</dt><dd>${ui.fmt(c.meta.fps)} fps</dd><dt>声音</dt><dd>${c.meta.audio?'原片有声音':'原片无音轨'}</dd><dt>来源</dt><dd>${c.provenance.type==='library'?'资产库固定版本':'本地副本'}</dd></dl>${assetVersionLink(c.provenance)}${p().assembly_source_parameters_version===1?sourceParametersMarkup(selectedItem?.run?.source_parameters||c.source_parameters):'<p class="helper">来源参数功能尚未加载，请重启导演台后查看。</p>'}`:'<p>选择视频后显示属性。</p>';
    const importPanel={id:'import',label:'导入',html:importOptions([`<button data-library ${disabled}>从资产库选择</button>`,`<button data-import ${disabled}>导入本地视频</button>`])+`<input type="file" data-files accept="video/*,.mkv" multiple hidden><p class="helper">两种来源均追加到当前视频目录，可多选后排序。</p>`};
    const panels=[...(step===0?[importPanel]:step===1&&e?referencePanels(p(),c,e,disabled):[]),{id:'source',label:'来源',html:sourcePanel},{id:'project',label:'项目',html:`${ui.field('项目名称',`<input data-name maxlength="120" value="${ui.esc(p().name)}" ${draftDisabled}>`)}<p>成片 ${p().assembly.output.width} × ${p().assembly.output.height} · ${p().assembly.output.fps} fps</p><p>${p().assembly.output.fit==='contain'?'等比例补边':'填满画布（裁切）'}</p><small>在顶部制作参数中调整。</small>`}];
    const inspector=propertyTabs(ctx,panels);
    let canvas='';
    if(step===0){
      canvas=selectedItem?.extension?`<div class="shot-heading"><h2>${ui.esc(selectedItem.name)}</h2><button data-edit-selected>查看续接与候选</button></div>${player(selectedItem.url)}<p class="helper">已选续接 · ${ui.fmt(selectedItem.seconds)}秒。左侧可单独调整顺序；更换候选后保留此轨道位置。</p>`:c?`<div class="shot-heading"><h2>${ui.esc(c.name)}</h2><button data-preview-range>预览使用范围</button></div>${player(c.url)}<div class="assembly-range">${ui.field('使用起点（秒）',`<input data-range="start" type="number" min="0" max="${c.meta.duration}" step=".001" value="${c.start}" ${draftDisabled}>`)}${ui.field('使用终点（秒）',`<input data-range="end" type="number" min="0" max="${c.meta.duration}" step=".001" value="${c.end}" ${draftDisabled}>`)}</div><p class="helper">只裁切项目使用范围，原文件保持完整。改变片尾后，关联续接需要重新选用。</p>`:`<div class="empty"><h2>先放入你的片段</h2><p>资产库与本地视频可以混合拼接，也可以只延长一个视频。</p><button data-open-import>打开导入页</button></div>`;
    }else if(step===1){
      canvas=`<div class="shot-heading"><h2>${ui.esc(c?.name||'尚未导入视频')}</h2><button data-add-extension ${!c||locked?'disabled':''}>＋ 添加续接</button></div><div class="assembly-extension-tabs">${c?.extensions.filter(x=>!x.removed_at).map((item,i)=>`<button data-extension="${item.id}" aria-pressed="${item.id===e?.id}">续写 ${i+1} · ${item.selected?'已选用':'待选用'}</button>`).join('')||''}</div>`;
      if(e){
        canvas+=`<div class="row between"><p>沿${c.extensions.filter(x=>!x.removed_at).indexOf(e)?'前一段已选续接':'当前视频使用范围'}的末尾继续生成</p><button class="text-link" data-remove-extension ${disabled}>移除续写段</button></div><p class="helper">修改描述或参数后，重新生成并选用才会改变成片；已选结果保留。</p><div class="row"><button data-preflight ${disabled}>检查工作流</button><button class="primary" data-generate ${disabled}>${runs.length?'重新生成':'生成续接'}</button></div>${ui.field('后续画面与声音描述',`<textarea data-prompt rows="4" ${draftDisabled}>${ui.esc(e.prompt)}</textarea>`)}${ui.field('希望新增时长（秒）',`<input data-seconds type="number" min="1" max="3600" step=".01" value="${e.seconds}" ${draftDisabled}>`,'内部会按模型合法帧数分段，交付只保留新增部分。')}${runView(r)}${candidates(r)}${player(r?.url)}${r?.state==='success'?resultActionBar({inspect:'<button data-play-tail>连播原片尾与续接</button>',decide:`<button data-select="${r.id}" ${locked||e.selected===r.id?'disabled':''}>${e.selected===r.id?'已选用':'选用此结果'}</button><button data-continue ${!e.selected||locked?'disabled':''}>沿已选结果继续续接</button>`,collect:resultActions(r)}):''}`;
      }else canvas+='<div class="empty"><h3>需要更长的镜头？</h3><p>添加续接并写下后续内容。不需要续接时，可以直接拼接导出。</p></div>';
    }else{
      canvas=`<h2>拼接成片</h2><ol>${track.map(v=>`<li>${ui.esc(v.name)} · ${ui.fmt(v.seconds)}秒</li>`).join('')}</ol><p>输出 ${p().assembly.output.width} × ${p().assembly.output.height} · ${p().assembly.output.fps} fps；${p().assembly.output.fit==='contain'?'等比例补边':'填满裁切'}。普通拼接不使用ComfyUI。</p><button class="primary" data-export ${locked||!c?'disabled':''}>开始拼接</button>${runView(r)}${candidates(r)}${player(r?.url)}${r?.state==='success'?resultActionBar({collect:resultActions(r)}):''}`;
    }
    const importing=p().assembly.runs.filter(v=>v.kind==='import').at(-1);
    if(step===0&&importing&&importing.state!=='success')canvas=runView(importing)+canvas;
    root.innerHTML=header+nav+(catalog.assembly_reference_version!==1?errorFeedback({kind:"website",message:"当前后台尚未加载续接参考素材能力，请在任务结束后重启导演台并刷新。"}):'')+`<div data-error>${error?errorFeedback(error):''}</div>`+workbench({rail,canvas:`<div class="assembly-content">${canvas}</div>`,inspector,kind:'assembly-desk'})+workspaceActions({support:`<button class="quiet" data-previous ${step===0?'disabled':''}>返回上一步</button><small data-save-state role="status">${draftStatus(session)}</small><button class="quiet" data-save ${session.working?'disabled':''}>保存草稿</button><button class="quiet" data-reload>刷新状态</button>`,actions:`${step===0?`<button data-direct ${!c?'disabled':''}>直接拼接导出</button>`:''}<button data-next class="primary" ${step===0&&!c?'disabled':''}>${step===0?'下一步：续接与挑选':step===1?'拼接导出':'返回视频与排序'}</button>`});
    asyncStatus.render();
    showSourceNavigation(root,sourceLocation);
    bindWorkspaceSteps(root);bindWorkbench(ctx);bindErrorFeedback(root);bind(c,e,r);bindAssemblyPrompts({root,session,extension:e,changed:setDirty,render});restoreView();disposePlayers.refresh();
    promptCollectionNotice(root,session);
    if(r)addRecordButton(root.querySelector('[data-ingest]')||root.querySelector('[data-play-tail]'),{path:'/records/'+p().id+'?run='+encodeURIComponent(r.id),signal:controller.signal,apply:e?row=>{if(session.disposed||extension()!==e||session.working)throw new Error('目标已变化或正在操作，请重新打开');e.prompt=row.content.text;recordSource(e,"prompt",row);setDirty();render();}:null});
  }
  function resultActions(r){return collectionActions({url:r.url,asset:r.asset,button:`<button data-ingest="${ui.esc(r.id)}" ${busy()?'disabled':''}>加入资产库</button>`});}
  function bind(c,e,r){
    bindReferences(root,{signal:controller.signal,p:p(),c,e,action,save,changed:setDirty,render,isDisposed:()=>session.disposed,importFile:async(data,file)=>{if(catalog.assembly_reference_version!==1)throw new Error('请重启导演台加载参考素材能力后再导入');let body={revision:p().revision,...data};if(file){const form=new FormData();Object.entries(body).forEach(([k,v])=>form.append(k,v));form.append('file',file);body=form;}session.project=await call('references',body);}});
    const on=(selector,event,fn)=>root.querySelectorAll(selector).forEach(el=>el.addEventListener(event,fn));
    on('[data-step]','click',event=>{step=Number(event.currentTarget.dataset.step);viewRun=null;render();});
    on('[data-track]','click',event=>{const item=trackItems(p()).find(row=>row.key===event.currentTarget.dataset.track);clipId=item.clip.id;extensionId=item.extension?.id||null;viewRun=item.run?.id||null;if(item.extension)ctx.inspectorTab='assets';render();});
    on('[data-edit-selected]','click',()=>{step=1;render();});
    on('[data-extension]','click',event=>{extensionId=event.currentTarget.dataset.extension;ctx.inspectorTab='assets';viewRun=null;render();});
    on('[data-next]','click',()=>{step=(step+1)%3;viewRun=null;render();});
    on('[data-previous]','click',()=>{step=Math.max(0,step-1);viewRun=null;render();});
    on('[data-direct]','click',()=>{step=2;viewRun=null;render();});
    const reorder=(key,offset)=>action(async()=>{await save();session.project=moveTrack(p(),key,offset);setDirty();await save();});
    on('[data-move]','click',event=>reorder(e?.selected?'extension:'+e.id:'clip:'+c.id,Number(event.currentTarget.dataset.move)));
    on('[data-drag]','dragstart',event=>{if(busy())return;event.dataTransfer.setData('text/plain',event.currentTarget.dataset.drag);});
    on('[data-drag]','dragover',event=>event.preventDefault());
    on('[data-drag]','drop',event=>{event.preventDefault();if(busy())return;const id=event.dataTransfer.getData('text/plain'),rows=trackItems(p()),from=rows.findIndex(v=>v.key===id),to=rows.findIndex(v=>v.key===event.currentTarget.dataset.drag);if(from<0||to<0)return;reorder(id,to-from);});
    on('[data-range]','change',event=>{c[event.target.dataset.range]=Number(event.target.value);setDirty();});
    on('[data-name]','input',event=>{p().name=event.target.value;setDirty();});
    on('[data-prompt]','input',event=>{e.prompt=event.target.value;setDirty();});
    on('[data-seconds]','change',event=>{e.seconds=Number(event.target.value);setDirty();});
    on('[data-save]','click',()=>action(save));
    on('[data-reload]','click',()=>action(async()=>{if(session.dirty&&!await ui.confirm('重新读取项目？','本地未保存草稿将被替换；服务器版本保留。','刷新'))return;await refresh();}));
    on('[data-open-import]','click',()=>{if(step===0){ctx.inspectorTab='import';ctx.inspectorHidden=false;render();}else addVideos(true);});
    on('[data-import]','click',()=>root.querySelector('[data-files]').click());
    on('[data-files]','change',event=>importFiles([...event.target.files]));
    on('[data-library]','click',()=>addVideos(false));
    on('[data-add-extension],[data-continue]','click',()=>action(async()=>{await save();session.project=await call('extensions',{revision:p().revision,clip:c.id});extensionId=clip().extensions.at(-1).id;ctx.inspectorTab='assets';viewRun=null;}));
    on('[data-remove-track]','click',()=>e?.selected?remove('extension',e.id):remove('clip',c.id));
    on('[data-remove-extension]','click',()=>remove('extension',e.id));
    on('[data-remove-run]','click',event=>remove('run',event.currentTarget.dataset.removeRun));
    on('[data-restore-run]','click',async event=>{const id=event.currentTarget.dataset.restoreRun;if(await ui.confirm('恢复生成记录',recordConfirmation(true),'恢复'))await mutate('visibility',{kind:'run',id,removed:false});});
    on('[data-run-view]','click',event=>{viewRun=event.currentTarget.dataset.runView;render();});
    on('[data-select]','click',event=>{const run=event.currentTarget.dataset.select;action(async()=>{await save();session.project=await call('select',{revision:p().revision,extension:e.id,run});viewRun=run;ui.toast('已加入左侧视频轨道，可调整顺序后拼接导出');});});
    on('[data-generate]','click',()=>mutate('generate',{extension:e.id}));
    on('[data-export]','click',()=>mutate('export',{}));
    on('[data-preflight]','click',()=>action(async()=>{await save();const result=await api(`/assembly/${p().id}/preflight/${e.id}`);if(result.issues.length)throw Object.assign(new Error(result.issues.join('；')),{kind:'compile'});ui.toast(`离线工作流检查通过 · ${result.parts.length}个内部任务 · 新增${ui.fmt(result.added_seconds)}秒，未提交生成`);}));
    on('[data-ingest]','click',event=>{const run=event.currentTarget.dataset.ingest;action(async()=>{await save();const result=await call('ingest',{revision:p().revision,run});session.project=result.project;ui.toast('已加入资产库');});});

    on('#settings','click',()=>{if(session.working){ui.toast('当前保存或导入尚未完成，请稍候。');return;}dialogBusy=true;settingsDialog({catalog,extension:e,signal:controller.signal,lastSeed:p().assembly.runs.filter(r=>r.extension===e?.id&&r.seed!=null).at(-1)?.seed,output:p().assembly.output,isDisposed:()=>session.disposed,onApply:async(next,output,saveNow)=>{if(next)Object.assign(e,next);p().assembly.output=output;setDirty();if(saveNow){session.working=true;try{await save();}finally{session.working=false;}}render();}}).finally(()=>dialogBusy=false);});
    on('[data-preview-range]','click',()=>{const video=root.querySelector('[data-media-player] video');video.currentTime=c.start;video.ontimeupdate=()=>{if(video.currentTime>=c.end)video.pause();};video.play().catch(err=>ui.toast(err.message));});
    on('[data-play-tail]','click',()=>{const source=r.snapshot.source,previous=p().assembly.runs.find(v=>v.file===source.file),original=p().assembly.clips.find(v=>v.file===source.file);const video=root.querySelector('[data-media-player] video');video.src=previous?.url||original?.url;video.onloadedmetadata=()=>{video.currentTime=Math.max(source.start,source.end-2);video.play().catch(err=>ui.toast(err.message));};video.ontimeupdate=()=>{if(video.currentTime>=source.end-.03){video.ontimeupdate=null;video.onloadedmetadata=()=>video.play().catch(()=>{});video.src=r.url;}};});
  }
  root.addEventListener('click',async event=>{const target=event.target.closest('[data-control]');if(!target||session.working)return;const {control:command,run}=target.dataset;if(await ui.confirm('处理当前任务？',command==='close'?'核对原提交后结束等待，记录保留，不会自动重试。':command==='recover'?'查询原提交并继续尚未完成的续接任务；不重复提交已登记任务。':'只停止当前任务，保留原件及已完成结果。','继续'))await action(async()=>{session.project=await call('control',{run,action:command,confirmed:true});});},{signal:controller.signal});
  render();
  const stopWatch=watchProject({
    get working(){return session.working;},get version(){return session.version;},
    get project(){return p();},get awaitingStatus(){return session.awaitingStatus;},set awaitingStatus(value){session.awaitingStatus=value;},controller,
    request:(path,method,body,signal)=>api(path,method,body,signal),
    receive(next){
      if(session.disposed||session.working||next.revision<p().revision)return;
      const change=pendingRefresh?'content':snapshotChange(p(),next,projectContent);
      if(change==='none')return;
      if(change==='status'||!canReplaceDraft(session,root)||dialogBusy){
        pendingRefresh=change==='content';
        mergeProjectRuntime(p(),next);
        if(change==='status'&&canReplaceDraft(session,root)&&!dialogBusy)acceptProjectRevision(p(),next);
        root.querySelectorAll('[data-assembly-run-state]').forEach(box=>{
          const run=next.assembly.runs.find(r=>r.id===box.dataset.assemblyRunState);
          if(run){const holder=document.createElement('template');holder.innerHTML=runView(run);updateStatusRegion(box,holder.content.firstElementChild.innerHTML);}
        });
        return;
      }
      pendingRefresh=false;session.project=next;
      render();
    },
    connection:asyncStatus.connection,
    emit(){},
  },()=>root.querySelectorAll('[data-clock]').forEach(el=>el.textContent=ui.elapsed(Number(el.dataset.clock),el.dataset.clockEnd?Number(el.dataset.clockEnd):null)));
  return {session,saveBeforeLeave:async()=>{await save();return !session.dirty;},dispose(){viewState.dispose();session.disposed=true;controller.abort();stopWatch();disposePlayers();root.querySelectorAll('video').forEach(v=>{v.pause();v.removeAttribute('src');v.load();});}};
}
