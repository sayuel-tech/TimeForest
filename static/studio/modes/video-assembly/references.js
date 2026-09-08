import {esc} from '../../ui/primitives.js';
import {chooseReferenceMetadata} from '../../ui/reference-metadata.js';
import {importOptions,referenceAssetCard} from '../../ui/reference-assets.js';
import {pickLibraryAsset} from '../../features/asset-picker/index.js';

export const boundReferences=(p,e)=>(e?.references||[]).map(row=>({...p.assembly.references?.find(a=>a.id===row.id),...row}));
export function referencePanels(p,c,e,disabled='') {
  const assets=boundReferences(p,e),active=c.extensions.filter(x=>!x.removed_at),previous=active[active.indexOf(e)-1];
  const imports=importOptions([
    `<label class="upload">本地图片<input data-reference-file="image" type="file" accept="image/png,image/jpeg,image/webp" multiple ${disabled}></label>`,
    `<label class="upload">本地声音<input data-reference-file="audio" type="file" accept="audio/*" multiple ${disabled}></label>`,
    `<button data-reference-library ${disabled}>从资产库选择</button>`,
    previous?`<button data-reference-inherit ${disabled}>沿用上一续写段素材</button>`:'',
  ]);
  const cards=assets.map(a=>referenceAssetCard(a,{actions:`<button class="quiet" data-reference-edit="${esc(a.id)}" ${disabled}>修改用途/角色</button><button class="quiet danger" data-reference-remove="${esc(a.id)}" ${disabled}>移除本段引用</button>`})).join('');
  const inventory=['image','audio'].flatMap(kind=>assets.filter(a=>a.kind===kind).map((a,i)=>`<li><strong>${kind==='image'?'Picture':'Audio'} ${i+1}</strong> · ${esc(a.name)} · ${esc(a.purpose)}${a.subject?' · 角色'+esc(a.subject):''}</li>`)).join('');
  return [{id:'assets',label:'素材',html:`<p class="helper">本段指定素材 · ${assets.length} 份</p>${imports}<div class="asset-list">${cards||'<p class="helper">可添加角色、服装、场景或音色参考；也可仅沿原片尾继续。</p>'}</div><p class="helper">资料PROMPT仅供存档，不会自动加入正文。新增素材用于下一次生成，已有候选保持。</p>`},
    {id:'sound',label:'声音',html:`<p>续接声音：${e.sound==='mute'?'续接静音':'生成声音'}</p><p class="helper">在顶部制作参数调整；不改变原视频声音。</p>${assets.filter(a=>a.kind==='audio').map(a=>referenceAssetCard(a)).join('')||'<p class="helper">尚无额外音色参考；片尾声音仍作为连续上下文。</p>'}`},
    {id:'inputs',label:'输入',html:`<h3>当前草稿输入</h3><ol>${inventory||'<li>无额外参考素材</li>'}</ol><p>尾部上下文：${previous?'上一续写段已选结果':'当前视频使用范围'}。</p><p class="helper">尾部声画不占Picture/Audio编号。素材增减后请核对正文编号；保存预检会检查实际绑定。</p>`}];
}
export function bindReferences(root,{p,c,e,action,save,importFile,changed,render,isDisposed,signal}) {
  // The selected extension survives step changes; its reference panel does not.
  const libraryButton=root.querySelector('[data-reference-library]');
  if(!e||!libraryButton)return;
  root.querySelectorAll('[data-reference-file]').forEach(input=>input.onchange=async()=>{
    const files=[...input.files],kind=input.dataset.referenceFile;input.value='';if(!files.length)return;
    const meta=await chooseReferenceMetadata({kind,signal});if(!meta||isDisposed())return;
    await action(async()=>{await save();for(const file of files)await importFile({extension:e.id,kind,...meta},file);});
  });
  root.querySelectorAll('[data-reference-edit]').forEach(button=>button.onclick=async()=>{
    const a=boundReferences(p,e).find(a=>a.id===button.dataset.referenceEdit);
    const meta=await chooseReferenceMetadata({kind:a.kind,initial:a,signal,title:'修改素材用途',applyLabel:'应用修改'});
    if(!meta||isDisposed())return;
    const row=e.references.find(x=>x.id===a.id);if(!row)return;
    Object.assign(row,meta);changed();render();
  });
  root.querySelectorAll('[data-reference-remove]').forEach(button=>button.onclick=()=>{e.references=e.references.filter(a=>a.id!==button.dataset.referenceRemove);changed();render();});
  const inherit=root.querySelector('[data-reference-inherit]');if(inherit)inherit.onclick=()=>{const rows=c.extensions.filter(x=>!x.removed_at),previous=rows[rows.indexOf(e)-1];e.references=structuredClone(previous.references||[]);changed();render();};
  libraryButton.onclick=async()=>{
    try {
    const item=await pickLibraryAsset({signal,title:'选择续接参考图片或声音'});if(!item||isDisposed())return;
    const media=item.snapshot.media.filter(m=>['image','audio'].includes(m.meta.kind));
    if(!media.length)throw new Error('所选版本没有图片或音频，请选择其他资产。');
    const meta=await chooseReferenceMetadata({media,signal,title:'确认本段参考'});if(!meta||isDisposed())return;
    const {media:mid,...purpose}=meta;
    await action(async()=>{await save();await importFile({extension:e.id,...purpose,reference:{asset:item.id,version:item.snapshot.id,media:mid}});});
    } catch(error) {if(!isDisposed())await action(async()=>{throw error;});}
  };
}
