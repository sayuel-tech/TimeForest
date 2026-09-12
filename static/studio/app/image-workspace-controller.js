import {imageSlots} from '../core/image-inputs.js';
import {workspaceViewState} from '../ui/workspace-view-state.js';
import {updateStatusRegion} from '../ui/status-region.js';
import {addRecordButton,recordSource} from '../features/prompt-library/records.js';
import {promptCollectionNotice} from '../features/prompt-library/collection.js';
import {bindImagePrompts} from '../features/prompt-library/adapters.js';
import {sourceTarget} from '../core/source-target.js';
import {showSourceNavigation} from '../ui/source-navigation.js';
import {uncertainMutation,requireKnownStatus} from '../core/async-state.js';
import {watchProject} from '../core/progress-channel.js';
import {asyncFeedback} from '../ui/async-feedback.js';
import {bindWorkspaceSteps} from '../ui/workspace-chrome.js';
import {draftStatus} from '../ui/draft-status.js';
import * as ui from '../ui/primitives.js';
import {recordConfirmation} from '../ui/candidate-records.js';
import {bindWorkbench,fitWorkbench} from '../ui/workbench.js';
import {ImageSession} from '../core/image-session.js';
import {ImageCanvas} from '../features/image-canvas/index.js';
import {pickLibraryAsset} from '../features/asset-picker/index.js';
import {libraryApi} from '../features/asset-picker/library-client.js';
import {sendToVideo} from '../features/image-results/transfer.js';
import {openImageSettings,imageParameters,readImageParameter} from '../features/image-settings/index.js';
import {errorFeedback,bindErrorFeedback} from '../ui/error-feedback.js';

import {renderImageWorkspace,imageActionBar,imageRunStatus,chosenOutput,generationReason,taskStatus} from '../features/image-results/workspace-view.js';

const presets={single:['将人物服装改为深绿色，保留人物身份、姿势、背景与构图。','将背景改为柔和的森林，保留人物整体形象。'],dual:['保留图A的场景、动作和构图，将图A人物的整体形象替换为图B人物，包括脸部、发型、服装、配饰与整体轮廓。','只将图A人物的脸部替换为图B的脸部，保留图A的发型、服装、动作、背景与构图。','将图B的服装用于图A人物，保留图A人物的脸部、动作和场景。'],region:['移除蓝色标注区域的物体，以周围自然背景填充。','将蓝色标注区域替换为：请描述新内容。保留其余构图。'],outpaint:['填充蓝色区域，自然延续原图的背景、光线与透视。保留原图人物与构图关系。']};
const presetNames={single:['修改服装','更换背景'],dual:['整体人物替换','只换脸','只换服装'],region:['移除物体','局部重绘'],outpaint:['自然延续'],text:[]};

export function mountWorkspace(root,project,catalog){
  const session=new ImageSession(project);let canvas=null,page=sessionStorage.getItem('image-page:'+project.id)||'edit',geom=null,geomSource=null,serial=0,timer=null,selection=null,submitKey=null;
  const viewState=workspaceViewState(root);
  const view={root,inspectorTab:'assets',inspectorHidden:false,tasksOpen:false,saveTarget:'new',assetName:'',feedback:'',error:false};
  const sourceLocation=sourceTarget(project);
  let viewingTask=sourceLocation?.state==='found'?sourceLocation.task:null;
  if(sourceLocation?.state==='found'){page=sourceLocation.page;selection=sourceLocation.output;view.inspectorTab=page==='results'?'result':'assets';}
  session.root=root;
  const asyncStatus=asyncFeedback(root,session.controller.signal);
  session.transferProgress=asyncStatus.transfer;session.connection=asyncStatus.connection;
  const base='/image-projects/'+project.id;
  const task=()=>session.project.tasks.find(t=>t.id===(viewingTask||session.project.current_task))||session.project.tasks[0];
  const input=id=>session.project.inputs.find(i=>i.id===id);
  const request=(path,method='GET',body)=>session.request(base+path,method,body);
  const context=()=>({project:session.project,task:task(),catalog,page,selection,view:Object.assign(view,{dirty:session.dirty}),presetNames});
  const mark=()=>{session.edit();refreshChrome();};
  const busy=()=>session.working||session.actionPending;
  function feedback(message,error=false){
    view.feedback=message;view.error=error;
    const box=root.querySelector('#image-feedback');
    if(box){
      if(error){box.innerHTML=errorFeedback(message);bindErrorFeedback(box);}else box.textContent=message;
      box.hidden=!message;box.classList.toggle('error',error);box.setAttribute('role',error?'alert':'status');fitWorkbench(root);
    }
  }
  function refreshChrome(){
    const saveState=root.querySelector('#image-save-state');
    if(saveState)saveState.textContent=draftStatus({dirty:session.dirty,working:busy()});
    for(const el of root.querySelectorAll('[data-action-disabled]')){el.disabled=false;delete el.dataset.actionDisabled;}
    if(!task()){
      asyncStatus.render();
    root.setAttribute('aria-busy',String(Boolean(busy())));
      const add=root.querySelector('#image-new');if(add)add.disabled=Boolean(busy());return;
    }
    const generate=root.querySelector('#image-generate'),reason=generationReason(session.project,task());
    const discard=root.querySelector('#image-task-discard');if(discard){discard.disabled=session.project.busy||catalog.task_discard_version!==1;discard.title=session.project.busy?'请先处理完成运行或待确认任务':catalog.task_discard_version!==1?'请重启导演台后刷新页面以加载任务废弃功能':'废弃当前任务及其候选，已入库资产保留';}
    const reroll=root.querySelector('#image-reroll');if(reroll){reroll.disabled=Boolean(reason);reroll.title=reason||'按当前任务原图、指令和参数再生成一个候选';}
    if(generate){generate.disabled=Boolean(reason);const hint=root.querySelector('#image-action-hint');if(hint)hint.textContent=reason||'生成时自动保存当前草稿。';}
    root.querySelectorAll('[data-view],[data-pen],[data-mask],#image-brush,#image-mask-visible').forEach(el=>el.disabled=!task().A);
    const swap=root.querySelector('#image-swap');if(swap)swap.disabled=!task().A||!task().B;
    const inputPrompt=root.querySelector('#image-input-prompt');if(inputPrompt)inputPrompt.textContent=task().prompt.trim()?'已填写':'尚未填写';
    const inputMask=root.querySelector('#image-input-mask');if(inputMask)inputMask.textContent=canvas?.changed?'标注已修改，尚未保存':task().mask?'已保存标注':'尚未保存标注';
    const maskState=root.querySelector('#image-mask-state');
    if(maskState){maskState.textContent=(canvas?.changed?(canvas.lastAction==='clear'?'已清空标注':'标注已修改')+'，尚未保存':task().mask?'已保存标注':'尚未标注')+' · 区域外可能变化。';}
    const status=root.querySelector('#image-task-status');if(status)status.textContent=taskStatus(session.project,task());
    const title=root.querySelector('#image-project-title');if(title){title.textContent=session.project.name;title.title=session.project.name;}
    asyncStatus.render();
    root.setAttribute('aria-busy',String(Boolean(busy())));
    if(busy())root.querySelectorAll('button,input,select,textarea').forEach(el=>{if(!el.disabled&&!el.matches('[data-copy-error]')){el.dataset.actionDisabled='true';el.disabled=true;}});
  }
  function selectProperty(id){
    view.inspectorTab=id;
    if(view.inspectorHidden)root.querySelector('[data-toggle-inspector]')?.click();
    root.querySelector(`[data-property-tab="${id}"]`)?.click();
    root.querySelector(`#property-${id}`)?.scrollIntoView({block:'nearest'});
  }
  async function action(fn){
    if(busy()||session.disposed)return;
    session.actionPending=true;feedback('');refreshChrome();
    try{await fn();}catch(e){if(!session.disposed&&e.name!=='AbortError')feedback(e,true);}
    finally{session.actionPending=false;if(!session.disposed)refreshChrome();}
  }
  async function flushMask(){
    if(!canvas?.changed)return;
    const t=task(),data=new FormData();data.append('file',await canvas.blob(),'mask.png');data.append('source',t.A);
    const record=await request('/inputs','POST',data);record.url=`/api/v5/projects/${project.id}/files/image_inputs/${record.id}/mask.png`;
    session.project.inputs.push(record);t.mask=record.id;canvas.changed=false;mark();
  }
  async function save(){await flushMask();await session.save();if(session.dirty)throw new Error('保存期间内容又有修改，请再保存一次后继续。');}
  async function showSettings(){
    const current=task(),taskId=current.id;
    const lastSeed=session.project.runs.filter(r=>r.task===taskId&&r.seed!==null&&r.seed!==undefined).at(-1)?.seed;
    await openImageSettings({task:current,catalog,lastSeed,signal:session.controller.signal,
      request:(...args)=>session.request(...args),onCatalog:next=>{catalog=next;},
      onApply:async(next,saveNow)=>{
        if(session.disposed||task().id!==taskId)throw new Error('当前编辑任务已变化，请重新打开制作参数。');
        // Keep the existing canvas, unsaved mask, prompt and outer draft alive.
        task().settings=next.settings;task().models=next.models;mark();
        root.querySelectorAll('[data-setting]').forEach(el=>{
          el.value=task().settings[el.dataset.setting];el.setCustomValidity('');
        });
        if(saveNow){await save();render();}else void geometry();
      }});
  }
  async function geometry(){
    const t=task(),source={taskId:t.id,A:t.A,submode:t.submode},epoch=++serial;geom=null;if(!t.A&&t.submode!=='text')return;
    try{const result=await request('/geometry','POST',{A:t.A,submode:t.submode,settings:t.settings});if(epoch!==serial||session.disposed)return;geom=result;geomSource=source;
      const box=root.querySelector('#image-dimensions');if(box)box.textContent=t.submode==='text'?`输出尺寸 ${result.output.join('×')}`:`工作图 ${result.work.join('×')} → 画布 ${result.canvas.join('×')} → 输出 ${result.output.join('×')}`;
      if(canvas){canvas.geometry=result;canvas.settings=t.settings;canvas.draw();canvas.fit();}
    }catch(e){if(epoch===serial){const box=root.querySelector('#image-dimensions');if(box)box.textContent=e.message;}}
  }
  function render(){
    if(session.disposed)return;
    const restoreView=viewState.beforeRender(JSON.stringify([session.project.id,page,task()?.id,selection]));
    sessionStorage.setItem('image-page:'+project.id,page);canvas?.dispose();canvas=null;
    const t=task();selection=chosenOutput(session.project,t,selection)?.id;
    root.className='page project-page image-workspace';root.innerHTML=renderImageWorkspace(context());showSourceNavigation(root,sourceLocation);
    root.querySelector('.desk-rail')?.setAttribute('aria-label','编辑任务');
    root.querySelector('.desk-inspector')?.setAttribute('aria-label','图片属性');
    root.querySelector('.property-tabs')?.setAttribute('aria-label','图片属性');
    if(!t){root.querySelector('#image-new').onclick=()=>void action(async()=>{newTask('single');render();});refreshChrome();restoreView();return;}
    bind();bindImagePrompts({root,session,task:t,changed:mark,render});
    promptCollectionNotice(root,session);
    if(selection)addRecordButton(root.querySelector('#image-reroll')||root.querySelector('#image-quick-ingest'),{path:'/records/'+project.id+'?output='+encodeURIComponent(selection),signal:session.controller.signal,apply:row=>{if(session.disposed||task()!==t||busy())throw new Error('目标已变化或正在操作，请重新打开');t.prompt=row.content.text;recordSource(t,"prompt",row);mark();page='edit';render();}});bindWorkspaceSteps(root);bindWorkbench(view);
    if(page==='edit'&&t.submode==='text')void geometry();
    if(page==='edit'&&t.submode!=='text'&&t.A){
      canvas=new ImageCanvas(root.querySelector('.image-viewport'),{image:input(t.A).url,mask:input(t.mask)?.url,mode:t.submode,settings:t.settings,geometry:geom,onChange:mark,onPad:(edge,value)=>{t.settings[edge]=value;mark();const field=root.querySelector(`[data-setting="${edge}"]`);if(field)field.value=value;void geometry();}});
      canvas.tool=t.submode==='region'?'brush':t.submode==='outpaint'?'expand':'pan';void geometry();
    }
    refreshChrome();restoreView();
  }
  function bind(){
    const bindAction=(selector,fn)=>root.querySelector(selector)?.addEventListener('click',()=>void action(fn));
    root.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>action(async()=>{await flushMask();page=b.dataset.page;view.inspectorTab=page==='edit'?'assets':'result';render();}));
    root.querySelectorAll('[data-task]').forEach(b=>b.onclick=()=>action(async()=>{await flushMask();viewingTask=null;session.project.current_task=b.dataset.task;selection=null;geom=null;view.assetName='';view.tasksOpen=false;mark();render();}));
    root.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>action(async()=>{await flushMask();const t=task();if(b.dataset.tool===t.submode)return;
      if(t.submode==='text'||b.dataset.tool==='text'){newTask(b.dataset.tool);}else if(session.project.runs.some(r=>r.task===t.id)){newTask(b.dataset.tool,t.A);}else{t.submode=b.dataset.tool;t.mask=null;t.B=null;for(const role of imageSlots.slice(2))delete t[role];mark();}geom=null;render();}));
    root.querySelectorAll('[data-upload-trigger]').forEach(b=>b.onclick=()=>root.querySelector(`[data-upload="${b.dataset.uploadTrigger}"]`)?.click());
    root.querySelector('.image-task-toggle')?.addEventListener('click',e=>{
      view.tasksOpen=!view.tasksOpen;e.currentTarget.setAttribute('aria-expanded',String(view.tasksOpen));
      e.currentTarget.textContent='当前：'+task().name+(view.tasksOpen?' · 收起任务':' · 展开任务');
      root.querySelector('.image-task-list').classList.toggle('is-open',view.tasksOpen);
    });
    root.querySelector('#image-open-assets')?.addEventListener('click',()=>selectProperty('assets'));
    bindAction('#image-settings',showSettings);
    root.querySelector('#image-asset-name')?.addEventListener('input',e=>{view.assetName=e.target.value;});
    root.querySelector('#image-save-target')?.addEventListener('change',e=>{view.saveTarget=e.target.value;root.querySelector('.savebar').innerHTML=imageActionBar(context());bindFooter();refreshChrome();});
    bindAction('#image-new' ,async()=>{await flushMask();newTask(task().submode);render();});
    root.querySelector('#image-project-name')?.addEventListener('input',event=>{session.project.name=event.target.value;mark();});
    bindAction('#image-task-discard',async()=>{
      if(catalog.task_discard_version!==1)throw new Error('请重启导演台后刷新页面以加载任务废弃功能');
      const current=task(),tid=current.id;
      if(session.project.busy)throw new Error('请先处理完成运行或待确认任务');
      if(!await ui.confirm('废弃「'+current.name+'」？','该任务及其候选将退出工作列表，并取消该任务的结果选用。已入库资产和视频引用保留，可在回收站“项目移除的”恢复。确认后保存当前草稿并废弃。','废弃任务'))return;
      if(session.disposed)return;
      await save();session.project=await request('/tasks/'+tid+'/discard','POST',{revision:session.project.revision});
      viewingTask=null;selection=null;submitKey=null;geom=null;view.assetName='';view.tasksOpen=true;view.inspectorTab='assets';page='edit';render();ui.toast('编辑任务已废弃');
    });
    bindAction('#image-task-name',async()=>{const name=await askText('任务名称',task().name);if(name){await flushMask();task().name=name;mark();render();}});
    root.querySelector('#image-prompt')?.addEventListener('input',e=>{task().prompt=e.target.value;mark();});
    root.querySelector('#image-preset')?.addEventListener('change',e=>void action(async()=>{if(e.target.value==='')return;const text=presets[task().submode][Number(e.target.value)];if(!text)return;if(task().prompt&&!(await ui.confirm('替换当前指令？','已写的指令会被示例替换，确认后仍可编辑。','替换')))return;task().prompt=text;mark();root.querySelector('#image-prompt').value=text;}));
    root.querySelectorAll('[data-setting]').forEach(el=>el.onchange=()=>{
      const key=el.dataset.setting,descriptor=imageParameters(task(),catalog).find(f=>f.scope==='settings'&&f.key===key);
      if(!descriptor)return;
      try{task().settings[key]=readImageParameter(descriptor,el.value);el.setCustomValidity('');feedback('');mark();void geometry();}
      catch(error){task().settings[key]=el.value;error.kind='input';el.setCustomValidity(error.message);mark();feedback(error,true);}
    });
    root.querySelectorAll('[data-upload]').forEach(el=>el.onchange=()=>action(async()=>{if(!el.files[0])return;await flushMask();const t=task(),role=el.dataset.upload,form=new FormData();form.append('file',el.files[0]);const ref=await request('/inputs','POST',form);ref.url=`/api/v5/projects/${project.id}/files/image_inputs/${ref.id}/image.png`;session.project.inputs.push(ref);t[role]=ref.id;if(role==='A')t.mask=null;mark();render();}));
    root.querySelectorAll('[data-library]').forEach(el=>el.onclick=()=>action(async()=>{const item=await pickLibraryAsset({signal:session.controller.signal,kind:'image',title:'选择图'+el.dataset.library});if(!item)return;await flushMask();await attachLibrary(item,el.dataset.library);render();}));
    root.querySelectorAll('[data-remove-input]').forEach(button=>button.onclick=()=>action(async()=>{
      const role=button.dataset.removeInput,t=task();
      if(!await ui.confirm('移除图 '+role+' 的引用？','只移除当前任务的输入引用，原文件、资产库和已有候选保留。'+(role==='A'?'该底图上的标注会一并清空。':''),'移除引用'))return;
      if(session.disposed)return;
      if(role!=='A')await flushMask();
      t[role]=null;if(role==='A'){t.mask=null;geom=null;}
      mark();render();
    }));
    bindAction('#image-add-reference',async()=>{
      if(catalog.multi_reference_version!==1)throw new Error('请重启导演台并刷新页面，加载多图保存接口。');
      const t=task(),role=imageSlots.slice(2).find(role=>!Object.hasOwn(t,role));
      if(!role)return;
      await flushMask();t[role]=null;mark();render();
      root.querySelector(`[data-upload-trigger="${role}"]`)?.focus();
    });
    root.querySelectorAll('[data-drop-image-slot]').forEach(button=>button.onclick=()=>action(async()=>{
      const role=button.dataset.dropImageSlot,t=task();
      if(t[role]&&!await ui.confirm('移除图 '+role+' 的引用和位置？','原文件、资产库和已有候选保留，其他图片编号不变。','移除引用'))return;
      if(session.disposed)return;
      await flushMask();delete t[role];mark();render();
    }));
    bindAction('#image-swap',async()=>{await flushMask();const t=task();[t.A,t.B]=[t.B,t.A];t.mask=null;mark();render();});
    root.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{if(!canvas)return;const type=b.dataset.view;if(type==='fit')canvas.fit();else canvas.setZoom(type==='actual'?1:canvas.zoom*(type==='plus'?1.25:.8));});
    root.querySelectorAll('[data-pen]').forEach(b=>b.onclick=()=>{if(canvas)canvas.tool=b.dataset.pen;root.querySelectorAll('[data-pen]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));});
    root.querySelectorAll('[data-mask]').forEach(b=>b.onclick=()=>{if(canvas){canvas.lastAction=b.dataset.mask;canvas.action(b.dataset.mask);}});
    root.querySelector('#image-brush')?.addEventListener('input',e=>{if(canvas)canvas.brush=Math.min(600,Math.max(1,Number(e.target.value)||1));});
    root.querySelector('#image-mask-visible')?.addEventListener('click',e=>{if(canvas){canvas.visible=!canvas.visible;canvas.draw();e.currentTarget.textContent=canvas.visible?'隐藏标注':'显示标注';e.currentTarget.setAttribute('aria-pressed',String(canvas.visible));}});
    root.querySelector('.image-viewport')?.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&['z','y'].includes(e.key.toLowerCase())){e.preventDefault();canvas?.action(e.key.toLowerCase()==='y'||e.shiftKey?'redo':'undo');}});
    const applyRatio=()=>{
      const t=task(),currentGeometry=geom||canvas?.geometry;
      // Outpaint work dimensions stay fixed while pads refresh; never reuse another task or image.
      if(!currentGeometry||t.submode!=='outpaint'||geomSource?.taskId!==t.id||geomSource.A!==t.A||geomSource.submode!==t.submode)return;
      const value=root.querySelector('#image-target-ratio')?.value;if(!value)return;const [w,h]=value.split(':').map(Number),[a,b]=currentGeometry.work,ratio=w/h;const dw=Math.max(0,Math.round(b*ratio-a)),dh=Math.max(0,Math.round(a/ratio-b));const anchor=root.querySelector('#image-anchor')?.value;const s=t.settings;s.left=anchor==='left'?0:anchor==='right'?dw:Math.floor(dw/2);s.right=dw-s.left;s.top=anchor==='top'?0:anchor==='bottom'?dh:Math.floor(dh/2);s.bottom=dh-s.top;['left','right','top','bottom'].forEach(k=>{const field=root.querySelector(`[data-setting="${k}"]`);if(field)field.value=s[k];});mark();void geometry();
    };
    root.querySelector('#image-target-ratio')?.addEventListener('change',applyRatio);root.querySelector('#image-anchor')?.addEventListener('change',applyRatio);
    bindAction('#image-reroll',generateImage);
    bindAction('#image-quick-ingest',async()=>{if(catalog.quick_ingest_preserves_selection!==true)throw new Error('当前后台未加载快捷入库，请重启导演台后刷新页面');await ingest(false,false);render();});
    bindAction('#image-continue',async()=>{await save();session.project=await request('/outputs/'+selection+'/continue','POST',{revision:session.project.revision});viewingTask=null;page='edit';selection=null;view.inspectorTab='assets';view.assetName='';render();});
    bindFooter();
    bindRunButtons();
    root.querySelectorAll('[data-record-remove],[data-record-restore]').forEach(b=>b.onclick=()=>action(async()=>{
      const restore=Boolean(b.dataset.recordRestore),record=b.dataset.recordRestore||b.dataset.recordRemove;
      if(!await ui.confirm(restore?'恢复生成记录':'移除这条生成记录？',recordConfirmation(restore),restore?'恢复':'移除'))return;
      await save();
      await session.request('/projects/'+project.id+'/records/visibility','POST',{record,removed:!restore,revision:session.project.revision});
      await session.reload();render();ui.toast(restore?'记录已恢复':'已移除，可在“已移除”中恢复');
    }));
    root.querySelectorAll('[data-output]').forEach(b=>b.onclick=()=>{selection=b.dataset.output;view.assetName='';render();});
    bindAction('#image-compare-toggle',async()=>{const box=root.querySelector('.image-compare');if(box.querySelector('[data-original]')){box.querySelector('[data-original]').remove();box.classList.remove('split');root.querySelector('#image-compare-toggle').setAttribute('aria-pressed','false');return;}const run=session.project.runs.find(r=>r.id===session.project.outputs.find(o=>o.id===selection)?.run),source=input(run?.snapshot.A||task().A);if(source){const g=run?.geometry;const aligned=run?.snapshot.submode==='outpaint'&&g;const original=aligned?`<div style="position:relative;aspect-ratio:${g.canvas[0]}/${g.canvas[1]};background:#cad2de;width:100%"><img src="${ui.esc(source.url)}" alt="原图在扩展画布中的位置" style="position:absolute;left:${g.offset[0]/g.canvas[0]*100}%;top:${g.offset[1]/g.canvas[1]*100}%;width:${g.work[0]/g.canvas[0]*100}%;height:${g.work[1]/g.canvas[1]*100}%"></div>`:`<img src="${ui.esc(source.url)}" alt="运行时图A">`;box.insertAdjacentHTML('afterbegin',`<figure data-original>${original}<figcaption>${aligned?'图A在扩展画布中的位置':'原图A（按原始比例）'}</figcaption></figure>`);box.classList.add('split');root.querySelector('#image-compare-toggle').setAttribute('aria-pressed','true');}});
  }
  async function generateImage(){requireKnownStatus(session);try{if(task().submode==='text'&&catalog.text_to_image_version!==1)throw new Error('请重启导演台后刷新页面以加载文生图');const reason=generationReason(session.project,task());if(reason)throw new Error(reason);await save();submitKey ||= crypto.randomUUID();await request('/tasks/'+task().id+'/generate','POST',{revision:session.project.revision,key:submitKey});submitKey=null;await session.reload();page='results';view.inspectorTab='result';render();}catch(error){uncertainMutation(session,error);throw error;}}
  function bindFooter(){
    const bindAction=(selector,fn)=>root.querySelector(selector)?.addEventListener('click',()=>void action(fn));
    root.querySelectorAll('.savebar [data-page]').forEach(b=>b.onclick=()=>action(async()=>{await flushMask();page=b.dataset.page;view.inspectorTab=page==='edit'?'assets':'result';render();}));
    bindAction('#image-save',async()=>{await save();ui.toast('草稿已保存');});
    bindAction('#image-check',async()=>{await save();const check=await request('/tasks/'+task().id+'/preflight');feedback(check.ready?'输入检查通过，可以开始生成。':{kind:'input',message:check.errors.join('；'),raw:check.errors.join('\n')},!check.ready);});
    bindAction('#image-generate',generateImage);
    bindAction('#image-select',async()=>{await save();session.project=await request('/outputs/'+selection+'/select','POST',{});page='use';view.inspectorTab='result';render();});
    bindAction('#image-ingest',async()=>{await ingest(false);render();});bindAction('#image-version',async()=>{await ingest(true);render();});
    bindAction('#image-send',async()=>{const out=session.project.outputs.find(o=>o.id===selection);let asset;if(out.library)asset=await libraryApi(`/assets/${out.library.asset}?version=${out.library.version}`);else{if(!(await ui.confirm('先保存到资产库','这张候选将保存为独立资产，随后选择目标视频项目。','保存并继续')))return;asset=await ingest(false);}if(asset)await sendToVideo(asset,session.controller.signal);});
  }
  function bindRunButtons(){bindErrorFeedback(root);root.querySelectorAll('[data-reconcile]').forEach(b=>b.onclick=()=>action(async()=>{await request('/runs/'+b.dataset.reconcile+'/reconcile','POST',{});ui.toast('正在核对原任务，不会重新提交');}));root.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=()=>action(async()=>{await request('/runs/'+b.dataset.cancel+'/cancel','POST',{});await session.reload();render();}));}
  function newTask(mode,A=null){viewingTask=null;const t={id:crypto.randomUUID(),name:'编辑任务 '+(session.project.tasks.length+1),submode:mode,A,B:null,mask:null,prompt:'',settings:structuredClone(catalog.defaults),models:{...catalog.models}};session.project.tasks.push(t);session.project.current_task=t.id;mark();page='edit';selection=null;view.assetName='';view.inspectorTab='assets';}
  async function attachLibrary(item,role,mediaId){
    const pictures=item.snapshot.media.filter(m=>m.meta.kind==='image');let media=pictures.find(m=>m.id===mediaId)||pictures.find(m=>m.role==='primary')||pictures[0];if(!media)throw new Error('此版本没有图片');
    if(pictures.length>1&&!mediaId){const selected=await chooseMedia(pictures);if(!selected)return;media=pictures.find(m=>m.id===selected);}
    const ref=await request('/library-input','POST',{asset:item.id,version:item.version,media:media.id});ref.url=`/api/v5/projects/${project.id}/files/image_inputs/${ref.id}/image.png`;if(!input(ref.id))session.project.inputs.push(ref);task()[role]=ref.id;if(role==='A')task().mask=null;mark();
  }
  async function ingest(existing,selectOutput=true){await save();let target=null;if(existing){target=await pickLibraryAsset({signal:session.controller.signal,kind:'image',title:'选择要添加新版本的资产'});if(!target)return null;if(!(await ui.confirm('添加资产版本',`目标：${target.snapshot.name}。当前版本 ${target.version.slice(0,8)}；原媒体保留，新图片成为当前版本的主媒体。`,'添加版本')))return null;}
    const asset=await request('/outputs/'+selection+'/library','POST',{asset:target?.id,revision:target?.revision,name:target?.snapshot.name||(view.assetName.trim()||task().name),select_output:selectOutput});await session.reload();ui.toast('已保存到资产库');return asset;}
  async function askText(title,value){return new Promise(resolve=>{const d=ui.modal(`<h2>${title}</h2><input maxlength="120" value="${ui.esc(value)}"><div class="dialog-actions"><button id="text-cancel">取消</button><button id="text-ok" class="primary">确定</button></div>`);d.oncancel=()=>resolve(null);d.querySelector('#text-cancel').onclick=()=>{d.close();resolve(null);};d.querySelector('#text-ok').onclick=()=>{const v=d.querySelector('input').value.trim();d.close();resolve(v);};});}
  async function chooseMedia(pictures){return new Promise(resolve=>{const d=ui.modal(`<h2>选择这个版本中的图片</h2><div class="image-candidates">${pictures.map(m=>`<button data-media-choice="${m.id}"><img src="${ui.esc(m.preview_url||m.url)}" alt="${ui.esc(m.name)}"><small>${ui.esc(m.name)}</small></button>`).join('')}</div><button id="media-cancel">取消</button>`);d.oncancel=()=>resolve(null);d.querySelector('#media-cancel').onclick=()=>{d.close();resolve(null);};d.querySelectorAll('[data-media-choice]').forEach(b=>b.onclick=()=>{d.close();resolve(b.dataset.mediaChoice);});});}
  const receive=p=>{
    const changed=session.receive(p);
    if(session.disposed)return;
    if(changed){render();return;}
    const box=root.querySelector('#image-run-state');
    if(box&&task()){updateStatusRegion(box,imageRunStatus(session.project,task()));bindRunButtons();}
    refreshChrome();
  };
  const resize=()=>fitWorkbench(root);window.addEventListener('resize',resize);
  render();
  const stopPoll=watchProject({get project(){return session.project;},get version(){return session.version;},get working(){return busy();},get disposed(){return session.disposed;},get awaitingStatus(){return session.awaitingStatus;},set awaitingStatus(value){session.awaitingStatus=value;},controller:session.controller,request:session.request.bind(session),receive,connection:asyncStatus.connection,emit(){}},()=>{});
  const stopClocks=ui.watchClocks(root);
  const incoming=new URLSearchParams(location.hash.split('?')[1]||'');
  if(incoming.get('asset'))void action(async()=>{const item=await libraryApi('/assets/'+encodeURIComponent(incoming.get('asset'))+'?version='+encodeURIComponent(incoming.get('version')||''));await attachLibrary(item,'A',incoming.get('media'));await save();render();history.replaceState(null,'','#/p/'+project.id);});
  return {session,saveBeforeLeave:async()=>{await save();return !session.dirty;},dispose(){viewState.dispose();stopPoll();clearTimeout(timer);stopClocks();serial++;canvas?.dispose();window.removeEventListener('resize',resize);session.dispose();}};
}
