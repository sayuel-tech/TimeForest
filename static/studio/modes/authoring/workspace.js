import {conversationKey} from '../../features/authoring-assist/conversation.js';
import {snapshotChange} from '../../core/snapshot-update.js';
import {projectContent,mergeProjectRuntime,acceptProjectRevision} from '../../contracts/project-refresh.js';
import {illustratedEmpty,bindDecorativeArt} from '../../ui/empty-state.js';
import {workspaceViewState} from '../../ui/workspace-view-state.js';
import {api} from '../../core/api-client.js';
import {esc,field,toast} from '../../ui/primitives.js';
import {workspaceHeader,workspaceSteps,bindWorkspaceSteps} from '../../ui/workspace-chrome.js';
import {workbench,propertyTabs,bindWorkbench} from '../../ui/workbench.js';
import {readingDisclosure} from '../../ui/prompt-editor.js';
import {workspaceActions} from '../../ui/workspace-actions.js';
import {confirmLeave,chooseAction} from '../../ui/choice-dialog.js';
import {draftStatus} from '../../ui/draft-status.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {shotSegmentTree} from '../../features/shot-segment-tree/index.js';
import {updateAssistStatus,mountAssist} from '../../features/authoring-assist/index.js';
import {mountReferences} from '../../features/authoring-assist/references.js';
import {profileMarkup,promptMarkup,bindAuthoringPromptTools} from '../../features/authoring-assist/prompt-fields.js';
import {watchProject} from '../../core/progress-channel.js';
import {canReplaceDraft} from '../../core/async-state.js';
import {readReturnContext,returnHref} from '../../features/shot-segment-tree/return-context.js';
import {showSourceNavigation} from '../../ui/source-navigation.js';
import {mountImageHandoffs} from '../../features/authoring-assist/image-handoffs.js';

const steps=[['0','故事起点'],['1','剧本创作'],['2','资产落实'],['3','分镜设计'],['4','片段 Prompt']];
const emptyContent={intent:{story_text:'',target_duration_seconds:null,reference_ids:[],preferences:''},screenplay:{blocks:[]},asset_screenplay:{blocks:[]},asset_bindings:{bindings:[],needs:[]},storyboard:{shots:[]},segment:{segments:[]}};
const key=()=>crypto.randomUUID();

export function mountWorkspace(root,initial) {
  const session={project:structuredClone(initial),dirty:false,working:false,actionPending:false,disposed:false};
  const ctx={root,session,inspectorTab:'references',expanded:new Set(),selected:'',step:0,pending:new Map(),dialoguePending:new Map(),assetTask:'asset_analysis',error:null};
  const controller=new AbortController();let saved=structuredClone(initial);
  const viewState=workspaceViewState(root);
  async function reload(){saved=await api('/projects/'+session.project.id,'GET',undefined,controller.signal);session.project=structuredClone(saved);}
  Object.assign(session,{controller,request:api,version:0,emit(){},receive(next){
    const change=snapshotChange(saved,next,projectContent);
    if(change==='none')return;
    if(canReplaceDraft(session,root)&&change==='content'){saved=structuredClone(next);session.project=next;render();}
    else {
      mergeProjectRuntime(session.project,next);updateAssistStatus(ctx);
      if(change==='status'&&canReplaceDraft(session,root)){saved=structuredClone(next);acceptProjectRevision(session.project,next);}
    }
  }});
  const stopWatching=watchProject(session,()=>{root.querySelectorAll('[data-clock]').forEach(el=>{if(!el.dataset.clockEnd){const secs=Math.max(0,Math.floor(Date.now()/1000-Number(el.dataset.clock)));el.textContent=`${Math.floor(secs/60)}分 ${secs%60}秒`;}});});
  const params=new URLSearchParams(location.hash.split('?')[1]||'');ctx.step=Math.max(0,Math.min(4,Number(params.get('step')||0)));ctx.selected=params.get('target')||'';
  const initialSegment=initial.content.layers.find(r=>r.layer==='segment')?.content.segments?.find(s=>s.ref===ctx.selected);
  if(initialSegment){ctx.expanded.add(initialSegment.shot_ref);if(ctx.step===3)ctx.selected=initialSegment.shot_ref;}
  if(initial.content.layers.some(r=>r.layer==='asset_screenplay'&&r.content.blocks?.length))ctx.assetTask='asset_screenplay';
  const row=(name,targets=[])=>{
    const exact=session.project.content.layers.find(x=>x.layer===name&&JSON.stringify(x.target_ids)===JSON.stringify(targets));if(exact)return exact;
    const collection={storyboard:'shots',segment:'segments'}[name],base=session.project.content.layers.find(x=>x.layer===name&&!x.target_ids.length);
    if(targets.length&&collection&&base)return {...base,target_ids:targets,content:{...base.content,[collection]:base.content[collection].filter(x=>targets.includes(x.ref))},content_hash:session.project.writing_target_hashes?.[name+':'+targets.join(',')]};
  };
  const content=(name,targets=[])=>row(name,targets)?.content||structuredClone(emptyContent[name]||{});
  const edit=(name,value,targets=[])=>{
    let found=row(name,targets);if(!found){found={layer:name,target_ids:targets,content_hash:null,content:{}};session.project.content.layers.push(found);}
    found.content=value;ctx.pending.set(JSON.stringify([name,targets]),found);session.dirty=true;status();
  };
  ctx.dialogue=scope=>session.project.writing_drafts?.[conversationKey(scope)]||{instruction:'',basis_candidate_id:null,include_images:false};
  ctx.editDialogue=(scope,patch)=>{const id=conversationKey(scope);session.project.writing_drafts||={};session.project.writing_drafts[id]={...ctx.dialogue(scope),...patch};ctx.dialoguePending.set(id,scope);session.dirty=true;status();};
  function status(){const el=root.querySelector('[data-draft-status]');if(el)el.textContent=draftStatus(session);}
  async function save(){
    if(session.project.creation_experience_version!==2)throw Error('当前服务尚未加载新版剧本接口。请保存好其他页面的工作后，通过导演台启动菜单重启服务，再使用此页面；当前输入保留。');
    if(session.working)return false;session.working=true;status();
    try{
      // Background job events advance the project revision without changing prose.
      // Rebase only if every edited layer still has its original content hash.
      const latest=await api('/projects/'+session.project.id,'GET',undefined,controller.signal);
      for(const entry of ctx.pending.values()){
        const remote=latest.content.layers.find(r=>r.layer===entry.layer&&JSON.stringify(r.target_ids)===JSON.stringify(entry.target_ids));
        if((remote?.content_hash||null)!==entry.content_hash)throw Error('这份正文已在其他窗口修改。当前输入仍保留，请先核对后再保存。');
      }
      for(const [id] of ctx.dialoguePending){if(JSON.stringify(saved.writing_drafts?.[id])!==JSON.stringify(latest.writing_drafts?.[id]))throw Error('沟通草稿已在其他窗口修改，当前输入保留');}
      const dialogueValues=structuredClone(session.project.writing_drafts||{});
      saved=latest;
      if(ctx.providerDraft){await api('/authoring/providers/save','POST',{request_key:key(),config:ctx.providerDraft});ctx.providerDraft=null;}
      for(const [id,entry] of [...ctx.pending]){
        const receipt=await api(`/authoring/projects/${session.project.id}/save`,'POST',{
          revision:saved.revision,request_key:key(),layer:entry.layer,target_ids:entry.target_ids,
          base_content_hash:entry.content_hash,update_mode:'replace_scope',removed_target_ids:[],content:entry.content},controller.signal);
        saved=await api('/projects/'+session.project.id,'GET',undefined,controller.signal);
        ctx.pending.delete(id);
        if(Object.keys(receipt.id_map).length){
          if(receipt.id_map[ctx.selected])ctx.selected=receipt.id_map[ctx.selected];
          for(const [oldId,newId] of Object.entries(receipt.id_map)){if(ctx.expanded.delete(oldId))ctx.expanded.add(newId);}
        }
      }
      for(const [id,scope] of ctx.dialoguePending){
        await api(`/authoring/projects/${session.project.id}/conversation`,'POST',{revision:saved.revision,request_key:key(),layer:scope.layer,target_ids:scope.targets,base_hash:saved.writing_draft_hashes?.[id]||null,draft:dialogueValues[id]},controller.signal);
        saved=await api('/projects/'+session.project.id,'GET',undefined,controller.signal);ctx.dialoguePending.delete(id);
      }
      session.project=structuredClone(saved);session.dirty=false;return true;
    }finally{session.working=false;status();}
  }
  async function run(fn){
    if(session.actionPending)return;session.actionPending=true;ctx.error=null;
    root.querySelectorAll('button').forEach(b=>b.disabled=true);
    try{await fn();}catch(error){ctx.error=error;}finally{session.actionPending=false;if(!session.disposed)render();}
  }
  async function leave(action){
    if(session.dirty){const choice=await confirmLeave({save,signal:controller.signal});if(!['save','discard'].includes(choice))return;
      if(choice==='discard'){ctx.pending.clear();ctx.dialoguePending.clear();ctx.providerDraft=null;session.project=structuredClone(saved);session.dirty=false;}}
    action();render();
  }
  function textarea(label,name,value,attrs=''){return field(label,`<textarea class="director-script" data-text="${name}" ${attrs}>${esc(value||'')}</textarea>`);}
  function prose(name,title){const value=content(name);return `<details class="saved-writing" data-view-key="saved:${name}"><summary>${esc(title)}</summary>${textarea('已保存内容',name,(value.blocks||[]).map(b=>[b.heading,b.text].filter(Boolean).join('\n')).join('\n\n'))}</details>`;}
  function navigate(step,target=''){ctx.step=Number(step);ctx.selected=target;ctx.splitShot=false;ctx.clipTask='prompt';ctx.viewCandidate=null;history.replaceState(null,'',`#/p/${session.project.id}?step=${ctx.step}${target?'&target='+encodeURIComponent(target):''}`);}
  function render(){
    if(session.disposed)return;
    const restoreView=viewState.beforeRender(JSON.stringify([session.project.id,ctx.step,ctx.selected]));
    const p=session.project,shots=content('storyboard').shots||[],segments=content('segment').segments||[];
    const review=(name,id)=>{const hash=session.project.writing_target_hashes?.[name+':'+id]||row(name,[id])?.content_hash;const c=p.content.confirmations.find(c=>c.layer===name&&c.target_id===id);return c?(c.review_state==='current'&&c.content_hash===hash?'已确认':'待核对'):'草稿';};
    const directoryShots=shots.map(s=>({...s,displayState:review('storyboard',s.ref)})),directorySegments=segments.map(s=>({...s,displayState:row('prompt',[s.ref])?review('prompt',s.ref):'待编写 Prompt'}));
    const shot=shots.find(s=>s.ref===ctx.selected),segment=segments.find(s=>s.ref===ctx.selected);
    let canvas='',rail='',inspector='';
    if(ctx.step===0){const intent=content('intent');canvas=`<h2>从一个想法开始</h2>${textarea('你的故事或创作想法','intent',intent.story_text)}${field('希望的时长（秒）',`<input data-duration type="number" min="1" step=".01" value="${intent.target_duration_seconds??''}" placeholder="尚未确定也可以继续">`)}${textarea('风格与创作偏好','preferences',intent.preferences)}`;}
    if(ctx.step===1)canvas=`<h2>完整剧本</h2>${readingDisclosure('故事起点',content('intent').story_text||'尚未填写')}<div data-authoring-assist></div>${prose('screenplay','已确认或保存的完整剧本 · 查看／编辑')}`;
    if(ctx.step===2)canvas=`<h2>剧本资产绑定</h2><div class="creation-asset-stage"><div data-reference-content></div></div><div class="creation-asset-writing"><h2>完整资产剧本</h2><div class="row"><button data-asset-task="asset_analysis">分析所需资产</button><button data-asset-task="asset_screenplay">创作完整资产剧本</button></div><div data-authoring-assist></div>${prose('screenplay','原完整剧本')}${prose('asset_screenplay','已保存的完整资产剧本 · 查看／编辑')}</div>`;
    if(ctx.step>=3){
      if(ctx.step===3){
        canvas=`<h2>${esc(shot?.title||'切分镜')}</h2>${readingDisclosure('完整资产剧本',(content('asset_screenplay').blocks||[]).map(b=>b.text).join('\n\n'))}${shot?`<div class="row"><button data-shot-task="rewrite">修改当前分镜</button><button data-shot-task="split">在本分镜下切片段</button></div>`:''}<div data-authoring-assist></div>${shot?`<details class="saved-writing"><summary>已保存分镜 · 查看／编辑</summary>${field('分镜名称',`<input data-shot-title value="${esc(shot.title||'')}">`)}${textarea('分镜内容','shot',shot.text)}${field('分镜默认视频工作流（H3）',`<select data-shot-recipe><option value="dance_split" ${shot.workflow_recipe!=='official_image'?'selected':''}>跳舞 8＋4</option><option value="official_image" ${shot.workflow_recipe==='official_image'?'selected':''}>官方工作流</option></select>`,'本分镜片段默认沿用；片段可单独更改。')}</details><button data-add-segment>手动添加片段</button>`:'<button data-add-shot>手动添加分镜</button>'}`;
      }else if(segment){const prompt=content('prompt',[segment.ref]),parent=shots.find(s=>s.ref===segment.shot_ref);canvas=`<h2>片段创作与 Prompt</h2>${readingDisclosure('本片段剧本依据',segment.text)}<div class="row"><button data-clip-task="rewrite">细化片段剧本</button><button data-clip-task="prompt">编写片段 Prompt</button></div><div data-authoring-assist></div><details class="saved-writing"><summary>已保存片段与 Prompt · 查看／编辑</summary>${textarea('片段内容','segment',segment.text)}${promptMarkup(prompt)}</details><details class="segment-options"><summary>工作流、时长与生成关系</summary>${profileMarkup(segment,{...prompt,profile_id:prompt.profile_id||`movie.${segment.dependency?.kind==='upstream_tail'?'tail':'independent'}.${parent?.workflow_recipe||'dance_split'}`})}${field('计划时长（秒）',`<input data-seconds type="number" min="1" step=".01" value="${segment.planned_seconds||5}">`)}${field('生成关系',`<select data-dependency><option value="">独立生成</option>${segments.filter(s=>s.ref!==segment.ref).map(s=>`<option value="${esc(s.ref)}" ${segment.dependency?.upstream_ref===s.ref?'selected':''}>续接：${esc(s.text?.slice(0,30)||'片段')}</option>`).join('')}</select>`)}</details>`;}
      else canvas='<div class="empty"><h2>选择一个片段</h2><p>先在分镜页切好片段，再从左侧目录进入。</p></div>';
    }
    rail=`<div class="creation-project-directory"><h3>创作目录</h3>${[['0','故事起点'],['1','完整剧本'],['2','完整资产剧本']].map(([step,title])=>`<button class="segment-tab ${ctx.step===Number(step)?'active':''}" data-nav-step="${step}">${title}</button>`).join('')}${shotSegmentTree({shots:directoryShots,segments:directorySegments,selected:ctx.step<3?'__other_page__':ctx.selected,expanded:ctx.expanded,fullLabel:'分镜设计'})}</div>`;
    if(ctx.step!==2)inspector=propertyTabs(ctx,[{id:'references',label:ctx.step>=3?'当前资产':'参考资产',html:`<div data-reference-content></div>`},{id:'project',label:'项目',html:`<h3>${esc(p.name)}</h3><p>可以随时保存未完成的剧本。</p><button data-import-movie>导入电影创作</button>`}]);
    root.className='page project-page authoring-page';
    root.innerHTML=workspaceHeader({name:p.name,code:'SCRIPT',modeName:'剧本创作',state:'draft',summary:'从故事到分镜与片段 Prompt',settings:{id:'authoring-settings',workflow:'云端写作设置'}})+workspaceSteps({items:steps,current:String(ctx.step),label:'剧本创作步骤'})+
      (ctx.error?errorFeedback(ctx.error):'')+workbench({rail,canvas,inspector,kind:'authoring-desk'+(ctx.step===2?' asset-binding-desk':'')})+
      workspaceActions({support:`<button data-save>保存草稿</button>${ctx.step?'<button data-back>返回上一步</button>':''}<span class="muted" data-draft-status>${draftStatus(session)}</span>`,actions:`${ctx.step!==4||segment?`<button data-confirm>${['确认故事起点','确认完整剧本','确认完整资产剧本',shot?'确认此分镜':'确认分镜设计','确认此片段 Prompt'][ctx.step]}</button>`:''}${ctx.step<4?'<button class="primary" data-next>下一步 →</button>':'<button class="primary" data-import-movie>导入电影创作 →</button>'}`});
    bindWorkspaceSteps(root);bindWorkbench(ctx);bindDecorativeArt(root);bindErrorFeedback(root);
    const back=readReturnContext(params);if(back)showSourceNavigation(root,{message:'从电影片段返回修改剧本。保存后回电影页核对同步，已有生成与剪辑保留。',returnHref:returnHref(back),returnLabel:'返回电影原片段'});
    root.querySelector('[data-save]').onclick=()=>run(async()=>{await save();toast('草稿已保存');});
    root.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>leave(()=>{navigate(b.dataset.tab);}));
    root.querySelector('[data-next]')?.addEventListener('click',()=>leave(()=>navigate(ctx.step+1,ctx.step===3?(segments.find(s=>s.shot_ref===ctx.selected)||segments[0])?.ref||'':'')));
    root.querySelector('[data-back]')?.addEventListener('click',()=>leave(()=>navigate(ctx.step-1)));
    root.querySelectorAll('[data-select]').forEach(b=>b.onclick=()=>leave(()=>navigate(segments.some(s=>s.ref===b.dataset.select)?4:3,b.dataset.select)));
    root.querySelectorAll('[data-nav-step]').forEach(b=>b.onclick=()=>leave(()=>navigate(b.dataset.navStep)));
    root.querySelectorAll('[data-asset-task]').forEach(b=>b.onclick=()=>leave(()=>{ctx.assetTask=b.dataset.assetTask;ctx.viewCandidate=null;}));
    root.querySelectorAll('[data-clip-task]').forEach(b=>b.onclick=()=>leave(()=>{ctx.clipTask=b.dataset.clipTask;ctx.viewCandidate=null;}));
    root.querySelectorAll('[data-shot-task]').forEach(b=>b.onclick=()=>leave(()=>{ctx.splitShot=b.dataset.shotTask==='split';ctx.viewCandidate=null;}));
    root.querySelectorAll('[data-expand]').forEach(b=>b.onclick=()=>{ctx.expanded.has(b.dataset.expand)?ctx.expanded.delete(b.dataset.expand):ctx.expanded.add(b.dataset.expand);render();});
    root.querySelectorAll('[data-text]').forEach(el=>el.oninput=()=>{
      const name=el.dataset.text;
      if(['intent','preferences'].includes(name)){const v=content('intent');v[name==='intent'?'story_text':'preferences']=el.value;edit('intent',v);}
      else if(['screenplay','asset_screenplay'].includes(name)){const v=content(name);if(!v.blocks?.length)v.blocks=[{ref:'tmp:'+key(),heading:'',text:''}];v.blocks.forEach((b,i)=>{b.heading='';b.text=i?'':el.value;});edit(name,v);}
      else if(name==='shot'){shot.text=el.value;edit('storyboard',{shots});}
      else if(name==='segment'){segment.text=el.value;edit('segment',{segments});}
      else if(name==='prompt')edit('prompt',{prompt_mode:'full',payload:{prompt_text:el.value,used_reference_keys:[]}},[segment.ref]);
    });
    root.querySelector('[data-duration]')?.addEventListener('input',e=>{const v=content('intent');v.target_duration_seconds=e.target.value?Number(e.target.value):null;edit('intent',v);});
    root.querySelector('[data-shot-recipe]')?.addEventListener('change',e=>{shot.workflow_recipe=e.target.value;edit('storyboard',{shots});});
    root.querySelector('[data-shot-title]')?.addEventListener('input',e=>{shot.title=e.target.value;edit('storyboard',{shots});});
    root.querySelector('[data-seconds]')?.addEventListener('input',e=>{segment.planned_seconds=Number(e.target.value);edit('segment',{segments});});
    root.querySelector('[data-dependency]')?.addEventListener('change',e=>{segment.dependency=e.target.value?{kind:'upstream_tail',upstream_ref:e.target.value}:{kind:'independent'};edit('segment',{segments});render();});
    root.querySelector('[data-authoring-profile]')?.addEventListener('change',async e=>{const profile=e.target.value,previous=content('prompt',[segment.ref]),mode=profile.endsWith('.structured')?'structured':'full';
      if(previous.prompt_mode&&previous.prompt_mode!==mode){const yes=await chooseAction({title:'更换正文方式',message:'会保留主描述，其他结构字段需要重新整理。已保存旧稿仍保留制作记录；取消不改变当前正文。',signal:controller.signal,choices:[{value:false,label:'取消'},{value:true,label:'更换并整理',primary:true}]});if(!yes){render();return;}}
      const text=previous.payload?.prompt_text||previous.payload?.fields?.prompt||'';edit('prompt',{profile_id:profile,prompt_mode:mode,payload:previous.prompt_mode===mode?previous.payload:mode==='full'?{prompt_text:text,used_reference_keys:[]}:{fields:{prompt:text},used_reference_keys:[]}},[segment.ref]);render();});
    root.querySelectorAll('[data-prompt-field]').forEach(el=>el.oninput=()=>{const value=content('prompt',[segment.ref]),kind=segment.dependency?.kind==='upstream_tail'?'tail':'independent';value.prompt_mode||='full';value.profile_id||=`movie.${kind}.dance_split`;value.payload||={used_reference_keys:[]};if(value.prompt_mode==='structured'){value.payload.fields||={};value.payload.fields[el.dataset.promptField]=el.value;}else value.payload.prompt_text=el.value;edit('prompt',value,[segment.ref]);});
    root.querySelector('[data-add-shot]')?.addEventListener('click',()=>run(async()=>{if(!await save())return;const list=content('storyboard').shots||[],ref='tmp:'+key();list.push({ref,title:`分镜 ${list.length+1}`,text:'',source_refs:[]});edit('storyboard',{shots:list});ctx.selected=ref;await save();ctx.expanded.add(ctx.selected);}));
    root.querySelector('[data-add-segment]')?.addEventListener('click',()=>run(async()=>{if(!await save())return;const list=content('segment').segments||[],ref='tmp:'+key();list.push({ref,shot_ref:ctx.selected,text:'',planned_seconds:5,start_state:'',end_state:'',dependency:{kind:'independent'}});edit('segment',{segments:list});ctx.expanded.add(ctx.selected);ctx.selected=ref;await save();ctx.step=4;}));
    if(root.querySelector('[data-confirm]'))root.querySelector('[data-confirm]').onclick=()=>run(async()=>{await save();const name=['intent','screenplay','asset_screenplay',segment?'segment':'storyboard','prompt'][ctx.step],targets=name==='prompt'||name==='storyboard'&&shot?[ctx.selected]:[],r=row(name,targets);if(!r)throw Error('请先填写当前内容');await api(`/authoring/projects/${p.id}/confirm`,'POST',{revision:saved.revision,request_key:key(),layer:name,target_ids:targets,content_hashes:{[name]:r.content_hash}});saved=await api('/projects/'+p.id);session.project=structuredClone(saved);toast('当前内容已确认');});
    root.querySelectorAll('[data-import-movie]').forEach(b=>b.onclick=()=>run(async()=>{if(!await save())return;const movie=await api('/movie/projects','POST',{request_key:key(),title:p.name+' · 电影',source_project_id:p.id,source_revision:saved.revision,segment_ids:[]});location.hash='/p/'+movie.id;}));
    mountAssist({ctx,content,edit,row,save,run,render,controller,reload});
    mountReferences({ctx,content,edit,save,run,render,reload,controller});
    mountImageHandoffs({ctx,content,row,save,run,render,reload,controller,returnContext:readReturnContext(params)});
    bindAuthoringPromptTools({ctx,controller,render});
    restoreView();
  }
  render();
  return {session,saveBeforeLeave:save,ctx,render,dispose(){session.disposed=true;stopWatching();viewState.dispose();controller.abort();}};
}
