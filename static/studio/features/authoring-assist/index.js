import {structuredOutput,bindStructuredOutput} from './output-editor.js';
import {writingScope,scopedJobs} from './conversation.js';
import {updateStatusRegion} from '../../ui/status-region.js';
import {creationJobStatus} from '../../ui/creation-job-status.js';
import {api} from '../../core/api-client.js';
import {esc,field,toast,scopedModal} from '../../ui/primitives.js';
import {openProductionSettings,productionSettingsMarkup,productionSettingsActions,bindSettingsNavigation} from '../../ui/production-settings.js';
import {candidateButton,resultActions} from '../../ui/result-view.js';
import {runTiming,runStatusRow} from '../../ui/run-timing.js';
import {removedRecords,recordConfirmation} from '../../ui/candidate-records.js';
import {chooseAction} from '../../ui/choice-dialog.js';

const key=()=>crypto.randomUUID();
const titles={screenplay_draft:'创作完整剧本',asset_analysis:'分析所需资产',asset_screenplay:'生成资产完整剧本',storyboard:'设计分镜',segment_plan:'整理生成片段',h3_prompt:'编写正式 Prompt',local_rewrite:'改写当前内容',context_summary:'整理上下文摘要',change_impact:'检查修改影响',image_observation:'描述参考图片',reference_image:'编写补图指令'};

export function updateAssistStatus(ctx){
  const scope=ctx.writingScope;if(!scope)return;
  const job=scopedJobs(ctx.session.project,scope).at(-1);
  updateStatusRegion(ctx.root.querySelector('[data-creation-status]'),creationJobStatus(job));
}

export function mountAssist({ctx,content,edit,row,save,run,render,controller,reload}){
  const root=ctx.root,p=ctx.session.project;
  root.querySelector('#authoring-settings').onclick=()=>settings(ctx,controller);
  const box=root.querySelector('[data-authoring-assist]');if(!box)return;
  const scope=writingScope(ctx,content);ctx.writingScope=scope;
  const draft=ctx.dialogue(scope);
  const tasks=ctx.step===1?['screenplay_draft']:ctx.step===2?[ctx.assetTask||'asset_analysis']:ctx.step===3?[ctx.splitShot?'segment_plan':ctx.selected?'local_rewrite':'storyboard']:ctx.step===4&&ctx.selected?[ctx.clipTask==='rewrite'?'local_rewrite':'h3_prompt']:[];
  const jobs=scopedJobs(p,scope);
  const current=jobs.at(-1);ctx.writingJob=current;
  const candidates=p.candidates.filter(c=>jobs.some(j=>j.job_id===c.job_id)&&c.disposition!=='discarded');
  const candidate=candidates.find(c=>c.candidate_id===ctx.viewCandidate)||candidates.at(-1);
  const editingSaved=candidate?.disposition==='applied'&&candidate===candidates.at(-1)&&scope.layer!=='asset_bindings';
  function savedOutput(){
    if(scope.layer==='prompt')return content('prompt',scope.targets).payload||candidate.payload;
    if(ctx.splitShot)return {segments:(content('segment').segments||[]).filter(s=>s.shot_ref===scope.targets[0])};
    return row(scope.layer,scope.targets)?.content||candidate.payload;
  }
  const displayPayload=editingSaved?savedOutput():candidate?.payload;
  function editSaved(payload){
    if(scope.layer==='prompt'){edit('prompt',{...content('prompt',scope.targets),payload},scope.targets);return;}
    const collection={screenplay:'blocks',asset_screenplay:'blocks',storyboard:'shots',segment:'segments'}[scope.layer];
    const value=content(scope.layer),updates=new Map(payload[collection].map(item=>[item.ref,item]));
    value[collection]=value[collection].map(item=>updates.get(item.ref)||item);edit(scope.layer,value);
  }
  box.innerHTML=`${tasks.length?`<div class="creation-assist"><h3>与 AI 沟通 · ${esc(ctx.step===1?'完整剧本':ctx.step===2?(ctx.assetTask==='asset_analysis'?'资产需求':'完整资产剧本'):ctx.step===3?(ctx.splitShot?'当前分镜切片段':'当前分镜'):'当前片段')}</h3><label class="field"><span>这次希望 AI 怎样帮助你</span><textarea data-ai-instruction placeholder="补充人物、节奏或需要改写的范围">${esc(draft.instruction||'')}</textarea></label><label class="check"><input data-include-images type="checkbox" ${draft.include_images?'checked':''}>附带参考图片（需要服务支持视觉输入）</label><div class="row">${tasks.map(t=>`<button data-ai-task="${t}" ${current&&['queued','running','submission_unknown'].includes(current.state)?'disabled':''}>${titles[t]}</button>`).join('')}</div></div>`:''}<h3>AI 输出</h3><div data-creation-status>${creationJobStatus(current)}</div><div class="row">${candidates.map((c,i)=>candidateButton({id:c.candidate_id,number:i+1,label:'文本候选',state:c.disposition==='applied'?'已应用':c.status==='needs_input'?'待补充':'待查看',viewing:c===candidate,attribute:'data-output'})).join('')}</div>${candidate?`<details data-view-key="candidate:${esc(candidate.candidate_id)}" open><summary>AI 返回的候选 · ${editingSaved?'已保存内容，可继续编辑':candidate.disposition==='applied'?'历史已应用输出':'尚未写入正文'}</summary>${displayPayload&&(displayPayload.blocks||displayPayload.replacement_text!==undefined||displayPayload.prompt_text!==undefined)?`<textarea class="director-script writing-output" data-candidate-text aria-label="本次输出">${esc(bodyText(displayPayload))}</textarea>`:`<div class="writing-output">${structuredOutput(displayPayload)}</div>`}${candidate.notes.length?`<details><summary>说明</summary><p>${esc(candidate.notes.join('\n'))}</p></details>`:''}${candidate.questions.map(q=>`<p>${esc(typeof q==='string'?q:q.question||q.text||'请补充必要资料')}</p>`).join('')}${resultActions({decide:`${editingSaved?'<button data-save-output>保存并确认修改</button>':''}${candidate.applicable&&candidate.disposition==='pending'?`<button data-apply-candidate>${scope.layer==='asset_bindings'?'确认资产需求，建立绑定卡片':'确认此输出'}</button>`:''}${candidate.disposition==='pending'?'<button class="quiet" data-discard-candidate>移除候选</button>':''}`})}</details>`:''}`;
  box.querySelector('[data-ai-instruction]')?.addEventListener('input',e=>ctx.editDialogue(scope,{instruction:e.target.value}));
  const input=box.querySelector('[data-ai-instruction]');
  if(input){input.closest('.field').insertAdjacentHTML('afterend',`<label class="field"><span>本次修改依据</span><select data-writing-basis><option value="">已保存内容</option>${candidates.map((c,i)=>`<option value="${c.candidate_id}" ${draft.basis_candidate_id===c.candidate_id?'selected':''}>本对象输出 ${i+1}</option>`).join('')}</select></label>`);box.querySelector('[data-writing-basis]').onchange=e=>ctx.editDialogue(scope,{basis_candidate_id:e.target.value||null});}
  if(jobs.length)box.insertAdjacentHTML('beforeend',`<details data-view-key="writing-history:${scope.layer}:${scope.targets.join(',')}"><summary>本对象沟通记录（${jobs.length}）</summary>${jobs.map(j=>`<section class="writing-round"><p>${esc(j.context.user_instruction)}</p><p class="helper">${esc(j.phase||j.state)}</p>${p.candidates.filter(c=>c.job_id===j.job_id&&c.disposition!=='discarded').map(c=>`<details><summary>查看这次输出</summary><div class="creation-prose">${esc(bodyText(c.payload))}</div></details>`).join('')}</section>`).join('')}</details>`);
  let editedPayload=null;
  box.querySelector('[data-candidate-text]')?.addEventListener('input',e=>{editedPayload=structuredClone(displayPayload);if(editedPayload.blocks){editedPayload.blocks.forEach((b,i)=>{b.heading='';b.text=i?'':e.target.value;});}else if('replacement_text' in editedPayload)editedPayload.replacement_text=e.target.value;else editedPayload.prompt_text=e.target.value;if(editingSaved)editSaved(editedPayload);else ctx.editDialogue(scope,{edited_candidate:{id:candidate.candidate_id,payload:editedPayload}});});
  if(candidate&&candidate.disposition==='applied'&&!editingSaved)box.querySelector('[data-candidate-text]')?.setAttribute('readonly','');
  if(!editingSaved&&candidate&&draft.edited_candidate?.id===candidate.candidate_id){editedPayload=draft.edited_candidate.payload;const output=box.querySelector('[data-candidate-text]');if(output)output.value=bodyText(editedPayload);}

  bindStructuredOutput(box,candidate?{...candidate,payload:displayPayload,disposition:editingSaved?'pending':candidate.disposition}:null,editedPayload,payload=>{editedPayload=payload;if(editingSaved)editSaved(payload);else ctx.editDialogue(scope,{edited_candidate:{id:candidate.candidate_id,payload}});});

  if(ctx.step===4&&ctx.selected&&content('segment').segments?.some(s=>s.ref===ctx.selected)){
    box.insertAdjacentHTML('beforeend','<button data-preview-formal>核对实际正文与素材编号</button>');box.querySelector('[data-preview-formal]').onclick=()=>run(async()=>{await save();const value=await api(`/authoring/projects/${p.id}/segments/${ctx.selected}/prompt-preview`);const d=scopedModal(`<h2>实际正文与输入绑定</h2><p>${esc(value.notice)}</p><div class="creation-prose">${esc(value.actual_prompt_text)}</div><h3>本次素材编号</h3>${value.input_contract.slots.map(s=>`<p>${esc(s.ordinal_label||'上游声画尾部')} · ${esc(s.purpose)} · ${esc(s.reference_key)}</p>`).join('')||'<p>没有参考素材输入。</p>'}<div class="dialog-actions"><button data-close>关闭</button></div>`);d.querySelector('[data-close]').onclick=()=>d.close();controller.signal.addEventListener('abort',()=>d.close(),{once:true});});
  }
  box.insertAdjacentHTML('beforeend',removedRecords(p.candidates.filter(c=>jobs.some(j=>j.job_id===c.job_id)).map(c=>({...c,id:c.candidate_id})),{preview:r=>'<span>文本候选</span>'}));
  box.querySelectorAll('[data-record-restore]').forEach(b=>b.onclick=()=>run(async()=>{await save();await api(`/projects/${p.id}/records/visibility`,'POST',{record:b.dataset.recordRestore,revision:ctx.session.project.revision,removed:false});await reload();}));
  if(current&&['queued','running','submission_unknown'].includes(current.state)){
    box.insertAdjacentHTML('beforeend','<button data-stop-writing>停止接收此请求</button>');box.querySelector('[data-stop-writing]').onclick=()=>run(async()=>{await api(`/authoring/jobs/${current.job_id}/cancel`,'POST',{job_id:current.job_id,request_key:key(),confirmed_scope:true});await reload();});
  }
  const artifact=current?.result_ref?p.artifacts[current.result_ref.id||current.result_ref]:null;
  if(artifact?.repair_eligible&&!current.repair_of){box.insertAdjacentHTML('beforeend','<button data-repair-response>修复此响应的格式</button><p class="helper">仅在你明确发起后另建云端请求；不会自动修复、补写或应用。</p>');box.querySelector('[data-repair-response]').onclick=()=>run(async()=>{const yes=await chooseAction({title:'另发一次格式修复请求',message:'将完整原响应交给当前云端服务重新整理格式。这是一次新的模型请求，成功后仍需核对并应用候选。',signal:controller.signal,choices:[{value:false,label:'取消'},{value:true,label:'发起格式修复',primary:true}]});if(!yes)return;await api('/authoring/jobs/repair','POST',{request_key:key(),job_id:current.job_id,repair_of:current.job_id,response_artifact_id:artifact.response_artifact_id,source_response_hash:artifact.response_hash});await reload();});}
  box.querySelector('[data-include-images]')?.addEventListener('change',e=>{ctx.editDialogue(scope,{include_images:e.target.checked});});
  box.querySelectorAll('[data-output]').forEach(b=>b.onclick=()=>{ctx.viewCandidate=b.dataset.output;render();});
  box.querySelectorAll('[data-ai-task]').forEach(b=>b.onclick=()=>run(async()=>{
    if(!await save())return;
    const task=b.dataset.aiTask,targets=scope.targets;
    const context=await api(`/authoring/projects/${p.id}/context`,'POST',{task_type:task,target_ids:targets,prompt_mode:task==='h3_prompt'?(content('prompt',[ctx.selected]).prompt_mode||'full'):null,layer:scope.layer,instruction:ctx.dialogue(scope).instruction?.trim()||titles[task],include_images:ctx.dialogue(scope).include_images},controller.signal);
    const providers=(await api('/authoring/providers')).items;const provider=providers.find(c=>c.provider_kind==='deepseek'&&c.enabled)||providers[0];
    await api('/authoring/jobs','POST',{request_key:key(),provider_config_id:provider.config_id,context,source_revision:ctx.session.project.revision,return_context:null},controller.signal);await reload();
  }));
  box.querySelector('[data-apply-candidate]')?.addEventListener('click',()=>run(async()=>{
    if(!await save())return;
    await api(`/authoring/projects/${p.id}/candidates/apply`,'POST',{request_key:key(),revision:ctx.session.project.revision,candidate_id:candidate.candidate_id,base_content_hash:candidate.base_content_hash,edited_payload:editedPayload});await reload();ctx.candidateEdit=null;
    if(scope.layer!=='asset_bindings'){
      const targetsList=scope.layer==='segment'&&ctx.splitShot?(content('segment').segments||[]).filter(s=>s.shot_ref===scope.targets[0]).map(s=>[s.ref]):[scope.targets];
      for(const targets of targetsList){const current=row(scope.layer,targets);
        if(current)await api(`/authoring/projects/${p.id}/confirm`,'POST',{revision:ctx.session.project.revision,request_key:key(),layer:scope.layer,target_ids:targets,content_hashes:{[scope.layer]:current.content_hash}});
        await reload();
      }
    }
    toast(scope.layer==='asset_bindings'?'资产需求已整理到绑定卡片':'输出已确认并保存');
  }));
  box.querySelector('[data-save-output]')?.addEventListener('click',()=>run(async()=>{
    if(!await save())return;
    const targetsList=scope.layer==='segment'&&ctx.splitShot?(content('segment').segments||[]).filter(s=>s.shot_ref===scope.targets[0]).map(s=>[s.ref]):[scope.targets];
    for(const targets of targetsList){const current=row(scope.layer,targets);if(current)await api(`/authoring/projects/${p.id}/confirm`,'POST',{revision:ctx.session.project.revision,request_key:key(),layer:scope.layer,target_ids:targets,content_hashes:{[scope.layer]:current.content_hash}});await reload();}
    toast('修改已保存并确认，历史输出保留');
  }));
  box.querySelector('[data-discard-candidate]')?.addEventListener('click',()=>run(async()=>{
    if(ctx.session.dirty)throw Error('请先保存当前正文');
    await api(`/authoring/projects/${p.id}/candidates/discard`,'POST',{request_key:key(),revision:p.revision,candidate_id:candidate.candidate_id,reason:'用户整理候选'});await reload();
  }));
}

export function bodyText(payload){
  if(!payload)return '';
  if(payload.blocks)return payload.blocks.map(b=>[b.heading,b.text].filter(Boolean).join('\n')).join('\n\n');
  if(payload.shots)return payload.shots.map(s=>[s.title,s.text].join('\n')).join('\n\n');
  if(payload.segments)return payload.segments.map(s=>s.text).join('\n\n');
  if(payload.needs)return payload.needs.map(n=>n.name+'：'+n.description).join('\n\n');
  if(payload.observations)return payload.observations.map(o=>o.reference_key+'\n'+o.visible_facts.join('\n')+'\n待确认：'+o.uncertainties.join('；')).join('\n\n');
  if(payload.impacts)return payload.impacts.map(i=>i.reason+'\n'+i.suggestion).join('\n\n');
  return payload.prompt_text||payload.replacement_text||payload.summary_text||payload.image_prompt_text||Object.values(payload.fields||{}).join('\n')||JSON.stringify(payload,null,2);
}

async function settings(ctx,controller){
  const modal=openProductionSettings({signal:controller.signal});
  try{
    const data=await api('/authoring/providers','GET',undefined,controller.signal);if(!modal.alive())return;
    const original=data.items.find(p=>p.provider_kind==='deepseek'),draft=structuredClone(ctx.providerDraft||original);let secret='';
    const render=()=>{
      modal.content.innerHTML=productionSettingsMarkup({scope:'云端写作服务 · 适用于剧本 AI 请求',sections:[{key:'provider',title:'服务与模型',html:`<div class="settings-grid">${field('服务地址',`<input data-config="base_url" value="${esc(draft.base_url)}">`)}${field('模型 ID',`<input data-config="model_id" value="${esc(draft.model_id||'')}">`,'测试型号临时提供；服务不可用时请手动更换，不会自动切换模型。')}${field('图片输入能力',`<select data-config="vision"><option value="unknown" ${draft.vision==='unknown'?'selected':''}>尚未确认</option><option value="supported" ${draft.vision==='supported'?'selected':''}>已确认支持</option><option value="unsupported" ${draft.vision==='unsupported'?'selected':''}>不支持</option></select>`)}${field('最大输出 token',`<input data-config="max_output_tokens" type="number" min="1" step="1" value="${draft.max_output_tokens}">`)}<label class="field"><span class="check"><input data-enabled type="checkbox" ${draft.enabled?'checked':''}>启用云端写作</span></label></div><p class="helper">保存配置不代表连接成功。本地 LLM 后续接入。</p>`},{key:'credential',title:'账户凭据',html:`${field('服务密钥',`<input data-secret type="password" autocomplete="new-password" placeholder="${original.credential_ref?'已配置，留空保留':'尚未配置'}">`)}<p class="helper">密钥只保存在网站后端，不进入剧本与提示词库。</p>`}],actions:productionSettingsActions([{role:'cancel',label:'取消'},{role:'apply',label:'应用'},{role:'save',label:'保存',primary:true}])});
      bindSettingsNavigation(modal.content,'provider');
      modal.content.querySelectorAll('[data-config]').forEach(el=>el.oninput=()=>{draft[el.dataset.config]=el.type==='number'?Number(el.value):el.value;});
      modal.content.querySelector('[data-enabled]').onchange=e=>draft.enabled=e.target.checked;
      modal.content.querySelector('[data-secret]').oninput=e=>secret=e.target.value;
      modal.content.querySelector('[data-settings-action=cancel]').onclick=modal.cancel;
      modal.content.querySelector('[data-settings-action=apply]').onclick=()=>modal.run(()=>{if(secret)throw Error('凭据需要点击保存写入后端');ctx.providerDraft=structuredClone(draft);ctx.session.dirty=true;ctx.root.querySelector('[data-draft-status]').textContent='有未保存的修改';toast('设置已应用到临时草稿，保存后用于请求');},{closeOnSuccess:true});
      modal.content.querySelector('[data-settings-action=save]').onclick=()=>modal.run(async()=>{
        await api('/authoring/providers/save','POST',{request_key:key(),config:draft});
        if(secret)await api('/authoring/providers/credential','POST',{request_key:key(),config_id:draft.config_id,secret});
        ctx.providerDraft=null;ctx.session.dirty=ctx.pending.size>0||ctx.dialoguePending.size>0;toast('云端写作设置已保存');
      },{closeOnSuccess:true});
    };render();
  }catch(error){modal.content.innerHTML='<div id="parameter-errors"></div>';modal.showError(error);}
}
