import {mountBindingCards} from './binding-cards.js';
import {api} from '../../core/api-client.js';
import {uploadForm} from '../../core/upload-client.js';
import {pickLibraryAsset} from '../asset-picker/index.js';
import {referenceAssetCard,importOptions} from '../../ui/reference-assets.js';
import {chooseReferenceMetadata} from '../../ui/reference-metadata.js';
import {esc,field,opts} from '../../ui/primitives.js';
import {chooseAction} from '../../ui/choice-dialog.js';

const key=()=>crypto.randomUUID();
export function mountReferences({ctx,content,edit,save,run,render,reload,controller}){
  const box=ctx.root.querySelector('[data-reference-content]');if(!box)return;
  if(ctx.step>=2){mountBindingCards({ctx,content,edit,save,run,render,reload,controller},box);return;}
  const refs=ctx.session.project.creation_references||[],bindings=content('asset_bindings');
  const needs=bindings.needs||[];
  box.innerHTML=importOptions(['<label class="upload">本地图片<input data-local-reference="image" type="file" accept="image/*" hidden></label>','<label class="upload">本地声音<input data-local-reference="audio" type="file" accept="audio/*" hidden></label>','<button data-library-reference>从资产库选择图片</button><button data-library-audio>从资产库选择声音</button>'])+
    '<p class="helper">本地参考在确认用途后入库并固定版本。资料说明不自动加入正文。</p>'+
    refs.map(r=>referenceAssetCard(r,{actions:`<button data-ref-edit="${r.id}">修改用途</button><button data-ref-remove="${r.id}">移除引用</button>`})).join('');
  async function attach(item,metadata){
    if(!await save())return;
    await api(`/authoring/projects/${ctx.session.project.id}/references`,'POST',{revision:ctx.session.project.revision,request_key:key(),asset:item.id,version:item.snapshot.id,media:metadata.media||item.snapshot.media[0].id,purpose:metadata.purpose,subject:metadata.subject});
    await reload();
  }
  box.querySelector('[data-library-reference]').onclick=async()=>{
    const item=await pickLibraryAsset({kind:'image',title:'选择剧本参考',signal:controller.signal});if(!item)return;
    const metadata=await chooseReferenceMetadata({media:item.snapshot.media,signal:controller.signal,title:'添加剧本参考'});if(!metadata)return;
    await run(()=>attach(item,metadata));
  };
  const visual=content('visual_references').references||[];
  if(visual.length){box.insertAdjacentHTML('beforeend',`<h3>视觉参考</h3><p class="helper">当前 H3 把这些图作为图片参考；不等于强制首尾帧。停用只修改此处的使用状态。</p>${visual.filter(v=>v.scope_target_id===ctx.session.project.id||v.scope_target_id===ctx.selected).map(v=>`<label class="check"><input data-visual-active="${v.id}" type="checkbox" ${v.active?'checked':''}>${esc({start:'起始画面',end:'结束画面',composition:'构图',key_state:'关键状态',atmosphere:'氛围'}[v.purpose]||v.purpose)} · ${v.scope_target_id===ctx.session.project.id?'全剧':'当前范围'} · ${esc(refs.find(r=>r.library_reference.asset===v.asset_ref)?.name||'固定资产')}</label>`).join('')}`);box.querySelectorAll('[data-visual-active]').forEach(el=>el.onchange=()=>{const value=content('visual_references');value.references.find(r=>r.id===el.dataset.visualActive).active=el.checked;edit('visual_references',value);});}
  box.querySelector('[data-library-audio]').onclick=async()=>{const item=await pickLibraryAsset({kind:'audio',title:'选择剧本声音参考',signal:controller.signal});if(!item)return;const metadata=await chooseReferenceMetadata({media:item.snapshot.media,signal:controller.signal,title:'添加声音参考'});if(metadata)await run(()=>attach(item,metadata));};
  box.querySelectorAll('[data-ref-edit]').forEach(b=>b.onclick=async()=>{const r=refs.find(r=>r.id===b.dataset.refEdit),metadata=await chooseReferenceMetadata({kind:r.kind,signal:controller.signal,title:'修改参考用途',initial:{purpose:r.purpose,subject:r.subject}});if(!metadata)return;await run(()=>attach({id:r.library_reference.asset,snapshot:{id:r.library_reference.version,media:[{id:r.library_reference.media}]}},metadata));});
  box.querySelectorAll('[data-ref-remove]').forEach(b=>b.onclick=async()=>{const yes=await chooseAction({title:'移除剧本引用',message:'只移除此剧本的素材引用，资产库原件和已有电影生成记录保留。仍有有效绑定的素材需要先停用绑定。',signal:controller.signal,choices:[{value:false,label:'取消'},{value:true,label:'移除引用',primary:true}]});if(!yes)return;await run(async()=>{await save();await api(`/authoring/projects/${ctx.session.project.id}/references/remove`,'POST',{revision:ctx.session.project.revision,request_key:key(),reference_id:b.dataset.refRemove});await reload();});});
  box.querySelectorAll('[data-local-reference]').forEach(input=>input.onchange=async()=>{
    const file=input.files[0];input.value='';if(!file)return;
    const metadata=await chooseReferenceMetadata({kind:input.dataset.localReference,signal:controller.signal,title:'导入本地参考并加入资产库'});if(!metadata)return;
    await run(async()=>{const form=new FormData();form.append('file',file);form.append('key','script-reference:'+key());
      const item=await uploadForm('/library/uploads',form,info=>{if(info){const status=ctx.root.querySelector('[data-draft-status]');if(status)status.textContent=info.phase;}},controller.signal);
      await attach(item,metadata);
    });
  });
}
