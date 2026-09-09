import {api} from '../../core/api-client.js';
import {esc,toast} from '../../ui/primitives.js';
import {pickLibraryAsset} from '../asset-picker/index.js';
import {chooseAction} from '../../ui/choice-dialog.js';

const key=()=>crypto.randomUUID();
export function mountImageHandoffs({ctx,content,save,run,reload,controller,returnContext}){
  const box=ctx.root.querySelector('[data-reference-content]');if(!box)return;
  const project=ctx.session.project,handoffs=project.image_handoffs||[];
  box.insertAdjacentHTML('beforeend',`<details class="image-handoffs" data-view-key="image-handoffs"><summary>补充视觉参考</summary><p class="helper">进入图片创作后添加素材和制作指令。完成并入库后，返回这里核对回填。</p><div class="image-handoff-actions"><button data-create-image-task>去图片模式补图</button></div>${handoffs.map((h,i)=>`<section class="image-handoff-item"><span class="helper">补图任务 ${i+1}</span><div class="image-handoff-actions"><a href="#/p/${esc(h.image_project_id)}">打开补图任务</a><button data-bind-image="${esc(h.handoff_id)}">选择已入库图片回填</button></div></section>`).join('')}</details>`);
  box.querySelector('[data-create-image-task]').onclick=async()=>{
    if(ctx.session.actionPending||ctx.session.working)return;
    const choice=await chooseAction({title:'是否保存当前草稿？',message:'保存或不保存后，都将进入图片创作；素材和制作指令在那里填写。',signal:controller.signal,choices:[{value:'discard',label:'不保存，前往图片创作'},{value:'save',label:'保存并前往图片创作',primary:true,run:save}]});
    if(!['save','discard'].includes(choice)||controller.signal.aborted)return;
    await run(async()=>{
      // A blank image workspace belongs to the saved project, not unsaved segment edits.
      const latest=await api(`/projects/${project.id}`,'GET',undefined,controller.signal);
      const context=await api(`/authoring/projects/${project.id}/context`,'POST',{task_type:'local_rewrite',layer:'intent',target_ids:[]});
      const response=await api(`/authoring/projects/${project.id}/image-handoffs`,'POST',{revision:latest.revision,request_key:key(),target:context.target,source_content_hash:context.base_content_hash,reference_purpose:'composition',image_prompt_text:'',reference_ids:[],return_context:returnContext});
      // Clear the leave guard only after creation succeeds; failures retain the draft.
      ctx.session.dirty=false;
      location.hash='/p/'+response.handoff.image_project_id;
    });
  };
  box.querySelectorAll('[data-bind-image]').forEach(button=>button.onclick=async()=>{
    const asset=await pickLibraryAsset({kind:'image',title:'选择补图的已入库版本',signal:controller.signal});if(!asset)return;
    const mode=await chooseAction({title:'回填方式',message:'备选保留现有参考；替换需要原剧本目标仍与补图时一致。',signal:controller.signal,choices:[{value:null,label:'取消'},{value:'append_alternative',label:'添加备选'},{value:'replace_active',label:'用作当前参考',primary:true}]});if(!mode)return;
    await run(async()=>{await save();const plan=await api(`/authoring/projects/${project.id}/image-bind/preflight`,'POST',{revision:ctx.session.project.revision,request_key:key(),handoff_id:button.dataset.bindImage,asset_ref:asset.id,asset_version:asset.snapshot.id,mode});
      const confirm=await chooseAction({title:'核对补图回填',message:plan.changes.map(c=>c.label+(c.source_changed?'（原正文已变化）':'')).join('；'),signal:controller.signal,choices:[{value:false,label:'取消'},{value:true,label:'确认回填',primary:true}]});if(!confirm)return;
      await api(`/authoring/projects/${project.id}/image-bind/apply`,'POST',{revision:ctx.session.project.revision,request_key:key(),plan_id:plan.plan_id,plan_hash:plan.plan_hash,selected_change_ids:plan.changes.map(c=>c.change_id)});await reload();toast('已固定所选资产版本并保存视觉参考');});
  });
}
