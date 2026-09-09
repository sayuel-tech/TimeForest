import {api} from '../../core/api-client.js';
import {uploadForm} from '../../core/upload-client.js';
import {pickLibraryAsset} from '../asset-picker/index.js';
import {esc,field,opts} from '../../ui/primitives.js';
import {chooseAction} from '../../ui/choice-dialog.js';

const key=()=>crypto.randomUUID();
const labels={character:'角色',scene:'场景',costume:'服装',prop:'道具',voice:'声音',style:'风格',other:'其他'};
export function resolveBindings(project,data,target=''){
  const segments=project.content.layers.find(r=>r.layer==='segment')?.content.segments||[];
  const segment=segments.find(s=>s.ref===target),shot=segment?.shot_ref||target;
  const chain=[['project',project.id],...(shot?[['shot',shot]]:[]),...(segment?[['segment',target]]:[])];
  return (data.needs||[]).map(need=>{
    let selected=null,base=null;
    for(const [kind,id] of chain){const policy=data.policies?.[id]||'parent';if(kind!=='project'){if(policy==='project')selected=base;else if(policy==='independent')selected=null;}
      const binding=data.bindings?.find(b=>b.need_ref===need.ref&&b.scope_kind===kind&&b.scope_ids.includes(id));
      if(binding){if(binding.source==='project')selected=base;else if(binding.state!=='inherit')selected=binding;}
      if(kind==='project')base=selected;
    }
    return selected||{need_ref:need.ref,state:'pending',scope_kind:'project',scope_ids:[]};
  });
}

export function mountBindingCards({ctx,content,edit,save,run,render,reload,controller},box){
  const p=ctx.session.project,data=content('asset_bindings'),needs=data.needs||[],target=ctx.step===2?'':ctx.selected;
  const segment=content('segment').segments?.find(s=>s.ref===target),scope=target?(segment?'segment':'shot'):'project',id=target||p.id;
  const refs=p.creation_references||[],effective=resolveBindings(p,data,target);
  const sourceLabel=b=>!b.scope_ids?.length?'尚未绑定':b.scope_kind==='project'?'全剧基础资产':b.scope_kind==='segment'?'本片段独立设定':`分镜「${content('storyboard').shots?.find(s=>b.scope_ids.includes(s.ref))?.title||'未命名'}」`;
  const lookup=b=>refs.find(r=>b.reference_id?r.id===b.reference_id:r.library_reference.asset===b.asset_ref&&r.library_reference.version===b.asset_version);
  const sourceHref=b=>`#/p/${p.id}?step=${b.scope_kind==='project'?2:b.scope_kind==='shot'?3:4}${b.scope_kind==='project'?'':'&target='+b.scope_ids[0]}`;
  const choices=segment?[['parent','沿用所属分镜'],['project','直接沿用全剧'],['independent','本片段独立设定']]:[['parent','沿用全剧'],['independent','本分镜独立设定']];
  box.innerHTML=`<h3>${scope==='project'?'资产需求与绑定':scope==='shot'?'本分镜资产':'本片段资产'}</h3>${target?field('基础来源',`<select data-asset-policy>${opts(choices,data.policies?.[id]||'parent')}</select>`):'<p class="helper">先分析需求，再把素材放入对应位置。已有参考可直接选入；解除绑定保留原件。</p>'}${needs.length?'<label class="check"><input type="checkbox" data-missing-only>只看待补资产</label>':'<p class="helper">尚无资产需求，请在完整资产剧本页发起分析，也可以手动补充。</p>'}<div class="asset-need-grid">${needs.map((n,i)=>{const b=effective[i],r=lookup(b);return `<section class="asset-need-card" data-need-card="${esc(n.ref)}" data-missing="${b.state==='pending'}"><span class="eyebrow">${esc(labels[n.kind]||n.kind)}</span><h3>${esc(n.name)}</h3><p>${esc(n.description)}</p>${r?`<a href="${esc(r.url)}" target="_blank" rel="noopener">${r.kind==='image'?`<img src="${esc(r.url)}" alt="${esc(r.name)}">`:esc(r.name)}</a>`:''}<p class="helper">${esc({pending:'待补充',bound:'已绑定',text_only:'仅用文字',disabled:'当前不使用',inherit:'沿用'}[b.state]||b.state)} · ${esc(sourceLabel(b))}</p>${b.scope_ids?.length?`<a class="quiet" href="${sourceHref(b)}">查看来源设定</a>`:''}<div class="asset-need-actions"><button data-need-pick="${esc(n.ref)}">${r?'更换素材':'从资产库选择'}</button><label class="upload">本地上传<input data-need-file="${esc(n.ref)}" type="file" accept="${['voice','audio','sound'].includes(n.kind)?'audio/*':'image/*'}" hidden></label></div><details><summary>使用关系与调整</summary>${field('素材来源',`<select data-need-source="${esc(n.ref)}">${opts([...(target?[['inherit','沿用基础来源'],...(segment?[['project','直接沿用全剧']]:[])]:[]),['bound','本处绑定'],['pending','解除绑定／待补'],['text_only','仅用文字'],['disabled','本处不使用']],data.bindings?.find(b=>b.need_ref===n.ref&&b.scope_ids.includes(id))?.source==='project'?'project':data.bindings?.find(b=>b.need_ref===n.ref&&b.scope_ids.includes(id))?.state||(target?'inherit':'pending'))}</select>`)}${field('使用说明',`<textarea data-need-text="${esc(n.ref)}">${esc(b.text_override||'')}</textarea>`)}${scope==='project'?`${field('需求名称',`<input data-need-name="${esc(n.ref)}" value="${esc(n.name)}">`)}${field('类别',`<select data-need-kind="${esc(n.ref)}">${opts(Object.entries(labels),n.kind)}</select>`)}${['costume','voice'].includes(n.kind)?field('关联角色',`<select data-need-subject_ref="${esc(n.ref)}">${opts([['','请选择角色'],...needs.filter(x=>x.kind==='character').map(x=>[x.ref,x.name])],n.subject_ref||'')}</select>`):''}${field('需求描述',`<textarea data-need-description="${esc(n.ref)}">${esc(n.description)}</textarea>`)}<button data-need-delete="${esc(n.ref)}">移除此需求</button>`:''}<p class="helper">只改变当前范围，不删除资产原件，不自动生成。</p></details></section>`;}).join('')}</div>${scope==='project'?'<button data-add-need>添加遗漏的资产需求</button>':''}`;

  const grid=box.querySelector('.asset-need-grid');grid.classList.replace('asset-need-grid','asset-need-groups');
  grid.dataset.viewScroll='';grid.id='asset-needs-scroll';
  for(const [kind,label] of Object.entries(labels)){
    const cards=needs.filter(n=>n.kind===kind).map(n=>box.querySelector(`[data-need-card="${CSS.escape(n.ref)}"]`));if(!cards.length)continue;
    const group=document.createElement('details');group.className='asset-need-group';group.open=true;group.dataset.viewKey='asset-kind:'+id+':'+kind;
    const done=needs.filter(n=>n.kind===kind&&effective.find(b=>b.need_ref===n.ref)?.state!=='pending').length;
    group.innerHTML=`<summary>${esc(label)} · 已落实 ${done} / ${cards.length}</summary><div class="asset-need-grid"></div>`;
    grid.append(group);cards.forEach(card=>group.querySelector('.asset-need-grid').append(card));
  }
  for(const need of needs){
    const card=box.querySelector(`[data-need-card="${CSS.escape(need.ref)}"]`),audio=need.kind==='voice';
    card.dataset.viewKey='asset-need:'+need.ref;
    const available=refs.filter(r=>r.kind===(audio?'audio':'image'));
    if(available.length){
      const details=document.createElement('details');details.innerHTML=`<summary>使用已提供的参考（${available.length}）</summary>${field('选择固定素材',`<select data-existing-reference>${opts(available.map(r=>[r.id,r.name+' · '+r.purpose+' '+r.subject]),available[0].id)}</select>`)}<button data-bind-existing>绑定到「${esc(need.name)}」</button>`;
      card.querySelector('.asset-need-actions').after(details);
      details.querySelector('[data-bind-existing]').onclick=()=>run(async()=>{const r=refs.find(r=>r.id===details.querySelector('select').value),item=await api('/library/assets/'+r.library_reference.asset+'?version='+encodeURIComponent(r.library_reference.version));await bindItem(need.ref,item);});
    }
    if(need.subject_ref){const person=needs.find(n=>n.ref===need.subject_ref);card.querySelector('h3').insertAdjacentHTML('afterend',`<p class="helper">关联角色：${esc(person?.name||'待指定')}</p>`);}
    if(need.source_text){const button=document.createElement('button');button.className='quiet';button.textContent='在剧本中查看使用位置';button.onclick=()=>{const area=ctx.root.querySelector('[data-text="screenplay"]');if(!area)return;area.closest('details').open=true;const start=area.value.indexOf(need.source_text);area.focus();if(start>=0)area.setSelectionRange(start,start+need.source_text.length);area.scrollIntoView({block:'center'});};card.append(button);}
    if(scope==='project'&&needs.length>1){const details=card.querySelector('details:last-of-type');details.insertAdjacentHTML('beforeend',`${field('重复需求可合并到',`<select data-merge-target><option value="">请选择保留的需求</option>${needs.filter(n=>n.ref!==need.ref&&n.kind===need.kind).map(n=>`<option value="${esc(n.ref)}">${esc(n.name)}</option>`).join('')}</select>`)}<button data-merge-need>合并此需求</button>`);
      details.querySelector('[data-merge-need]').onclick=async()=>{const dest=details.querySelector('[data-merge-target]').value;if(!dest)return;const yes=await chooseAction({title:'合并重复需求',message:'保留目标需求的名称及已有绑定；目标未绑定的范围沿用此需求的绑定。资产原件与历史版本保留。',signal:controller.signal,choices:[{value:false,label:'取消'},{value:true,label:'合并',primary:true}]});if(!yes)return;const v=content('asset_bindings');for(const b of v.bindings||[]){if(b.need_ref!==need.ref)continue;const clash=v.bindings.find(x=>x.need_ref===dest&&x.scope_kind===b.scope_kind&&JSON.stringify(x.scope_ids)===JSON.stringify(b.scope_ids));if(!clash)b.need_ref=dest;}
        v.bindings=(v.bindings||[]).filter(b=>b.need_ref!==need.ref);v.needs=v.needs.filter(n=>n.ref!==need.ref);for(const n of v.needs)if(n.subject_ref===need.ref)n.subject_ref=dest;edit('asset_bindings',v);render();};
    }
  }
  function binding(ref){const value=content('asset_bindings');value.bindings||=[];let b=value.bindings.find(b=>b.need_ref===ref&&b.scope_kind===scope&&b.scope_ids.includes(id));if(!b){b={id:'tmp:'+key(),need_ref:ref,scope_kind:scope,scope_ids:[id],usage:needs.find(n=>n.ref===ref).kind,state:'pending',asset_ref:null,asset_version:null,text_override:''};value.bindings.push(b);}return [value,b];}
  box.querySelector('[data-asset-policy]')?.addEventListener('change',e=>{const v=content('asset_bindings');v.policies||={};v.policies[id]=e.target.value;edit('asset_bindings',v);render();});
  box.querySelector('[data-missing-only]')?.addEventListener('change',e=>box.querySelectorAll('[data-need-card]').forEach(card=>card.hidden=e.target.checked&&card.dataset.missing!=='true'));
  box.querySelectorAll('[data-need-source]').forEach(el=>el.onchange=()=>{const [v,b]=binding(el.dataset.needSource);b.source=el.value==='project'?'project':el.value==='inherit'?'parent':'independent';b.state=el.value==='project'?'inherit':el.value;edit('asset_bindings',v);render();});
  box.querySelectorAll('[data-need-text]').forEach(el=>el.oninput=()=>{const [v,b]=binding(el.dataset.needText);const inherited=effective.find(x=>x.need_ref===el.dataset.needText);if(inherited?.state==='bound'&&b.state!=='bound')Object.assign(b,{state:'bound',asset_ref:inherited.asset_ref,asset_version:inherited.asset_version,reference_id:inherited.reference_id});b.text_override=el.value;b.source='independent';if(b.state==='inherit'||b.state==='pending')b.state='text_only';edit('asset_bindings',v);});
  for(const field of ['name','description','kind','subject_ref'])box.querySelectorAll(`[data-need-${field}]`).forEach(el=>el.onchange=()=>{const v=content('asset_bindings');v.needs.find(n=>n.ref===el.getAttribute('data-need-'+field))[field]=el.value;edit('asset_bindings',v);render();});
  async function bindItem(needRef,item){
    const index=content('asset_bindings').needs.findIndex(n=>n.ref===needRef);
    if(!await save())return;
    needRef=content('asset_bindings').needs[index]?.ref;
    const need=content('asset_bindings').needs.find(n=>n.ref===needRef);if(!need)throw Error('需求已变化，请重新选择');
    const purpose=['voice','audio','sound'].includes(need.kind)?'voice':({character:'character',costume:'costume',scene:'scene',style:'palette',palette:'palette',prop:'prop'})[need.kind]||'scene';
    const people=content('asset_bindings').needs.filter(n=>n.kind==='character');
    if(['costume','voice'].includes(purpose)&&!people.some(n=>n.ref===need.subject_ref))throw Error('请先在使用关系中指定该素材关联的角色');
    const subject=['voice','character','costume'].includes(purpose)?String(people.findIndex(n=>n.ref===(purpose==='character'?needRef:need.subject_ref))+1):'';
    const receipt=await api(`/authoring/projects/${p.id}/references`,'POST',{revision:ctx.session.project.revision,request_key:key(),asset:item.id,version:item.snapshot.id,media:item.snapshot.media.find(m=>m.role==='primary')?.id||item.snapshot.media[0].id,purpose,subject,binding_need_ref:needRef});
    await reload();const r=ctx.session.project.creation_references.find(r=>r.id===receipt.changed_ids[0]),[v,b]=binding(needRef);Object.assign(b,{state:'bound',source:'independent',asset_ref:item.id,asset_version:item.snapshot.id,reference_id:r.id});edit('asset_bindings',v);await save();
  }
  box.querySelectorAll('[data-need-pick]').forEach(button=>button.onclick=async()=>{const n=needs.find(n=>n.ref===button.dataset.needPick),item=await pickLibraryAsset({kind:['voice','audio','sound'].includes(n.kind)?'audio':'image',title:'为「'+n.name+'」选择素材',signal:controller.signal});if(item)await run(()=>bindItem(n.ref,item));});
  async function upload(ref,file){if(!file)return;await run(async()=>{const index=content('asset_bindings').needs.findIndex(n=>n.ref===ref);if(!await save())return;ref=content('asset_bindings').needs[index].ref;const form=new FormData();form.append('file',file);form.append('key','need:'+key());const item=await uploadForm('/library/uploads',form,()=>{},controller.signal);await bindItem(ref,item);});}
  box.querySelectorAll('[data-need-file]').forEach(el=>el.onchange=()=>upload(el.dataset.needFile,el.files[0]));
  box.querySelectorAll('[data-need-card]').forEach(card=>{card.ondragover=e=>{e.preventDefault();};card.ondrop=e=>{e.preventDefault();void upload(card.dataset.needCard,e.dataTransfer.files[0]);};});
  box.querySelector('[data-add-need]')?.addEventListener('click',()=>{const v=content('asset_bindings');v.needs||=[];v.needs.push({ref:'tmp:'+key(),kind:'other',name:'新资产',description:'填写用途与特征',source_refs:[],media_need:'recommended',suggested_asset_refs:[]});edit('asset_bindings',v);render();});
  box.querySelectorAll('[data-need-delete]').forEach(b=>b.onclick=async()=>{const yes=await chooseAction({title:'移除此需求？',message:'将移除此需求及各范围的绑定，保留资产原件和历史版本。',signal:controller.signal,choices:[{value:false,label:'取消'},{value:true,label:'移除需求',primary:true}]});if(yes){const v=content('asset_bindings');if(v.needs.some(n=>n.subject_ref===b.dataset.needDelete)){ctx.error=Error('此角色仍关联服装或声音，请先调整这些需求的关联角色');render();return;}v.needs=v.needs.filter(n=>n.ref!==b.dataset.needDelete);v.bindings=(v.bindings||[]).filter(x=>x.need_ref!==b.dataset.needDelete);edit('asset_bindings',v);render();}});
}
