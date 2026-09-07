import {esc,opts,field,scopedModal} from '../../ui/primitives.js';
import {importOptions,referenceAssetCard} from '../../ui/reference-assets.js';
import {pickLibraryAsset} from '../../features/asset-picker/index.js';

const purposes=[['character','角色'],['face','脸部'],['costume','服装'],['scene','场景'],['palette','色系'],['prop','道具']];
export const boundReferences=(p,e)=>(e?.references||[]).map(row=>({...p.assembly.references?.find(a=>a.id===row.id),...row}));
export function referencePanels(p,c,e,disabled='') {
  const assets=boundReferences(p,e),active=c.extensions.filter(x=>!x.removed_at),previous=active[active.indexOf(e)-1];
  const imports=importOptions([
    `<label class="upload">本地图片<input data-reference-file="image" type="file" accept="image/png,image/jpeg,image/webp" multiple ${disabled}></label>`,
    `<label class="upload">本地声音<input data-reference-file="audio" type="file" accept="audio/*" multiple ${disabled}></label>`,
    `<button data-reference-library ${disabled}>从资产库选择</button>`,
    previous?`<button data-reference-inherit ${disabled}>沿用上一续写段素材</button>`:'',
  ]);
  const cards=assets.map(a=>referenceAssetCard(a,{actions:`${field('素材用途',`<select data-reference-purpose="${a.id}" ${disabled}>${opts(a.kind==='audio'?[['voice','音色参考']]:purposes,a.purpose)}</select>`)}${field('角色ID',`<input data-reference-subject="${a.id}" value="${esc(a.subject)}" inputmode="numeric" ${disabled}>`)}<button class="quiet danger" data-reference-remove="${a.id}" ${disabled}>移除本段引用</button>`})).join('');
  const inventory=['image','audio'].flatMap(kind=>assets.filter(a=>a.kind===kind).map((a,i)=>`<li><strong>${kind==='image'?'Picture':'Audio'} ${i+1}</strong> · ${esc(a.name)} · ${esc(a.purpose)}${a.subject?' · 角色'+esc(a.subject):''}</li>`)).join('');
  return [{id:'assets',label:'素材',html:`<p class="helper">本段指定素材 · ${assets.length} 份</p>${imports}<div class="asset-list">${cards||'<p class="helper">可添加角色、服装、场景或音色参考；也可仅沿原片尾继续。</p>'}</div><p class="helper">资料PROMPT仅供存档，不会自动加入正文。新增素材用于下一次生成，已有候选保持。</p>`},
    {id:'sound',label:'声音',html:`<p>续接声音：${e.sound==='mute'?'续接静音':'生成声音'}</p><p class="helper">在顶部制作参数调整；不改变原视频声音。</p>${assets.filter(a=>a.kind==='audio').map(a=>referenceAssetCard(a)).join('')||'<p class="helper">尚无额外音色参考；片尾声音仍作为连续上下文。</p>'}`},
    {id:'inputs',label:'输入',html:`<h3>当前草稿输入</h3><ol>${inventory||'<li>无额外参考素材</li>'}</ol><p>尾部上下文：${previous?'上一续写段已选结果':'当前视频使用范围'}。</p><p class="helper">尾部声画不占Picture/Audio编号。素材增减后请核对正文编号；保存预检会检查实际绑定。</p>`}];
}
export function bindReferences(root,{p,c,e,action,save,importFile,changed,render,isDisposed}) {
  // The selected extension survives step changes; its reference panel does not.
  const libraryButton=root.querySelector('[data-reference-library]');
  if(!e||!libraryButton)return;
  root.querySelectorAll('[data-reference-file]').forEach(input=>input.onchange=()=>{const files=[...input.files],kind=input.dataset.referenceFile;action(async()=>{await save();for(const file of files)await importFile({extension:e.id,kind},file);});});
  root.querySelectorAll('[data-reference-purpose],[data-reference-subject]').forEach(input=>input.onchange=()=>{const purpose=input.dataset.referencePurpose,id=purpose||input.dataset.referenceSubject;const row=e.references.find(x=>x.id===id);row[purpose?'purpose':'subject']=input.value;changed();});
  root.querySelectorAll('[data-reference-remove]').forEach(button=>button.onclick=()=>{e.references=e.references.filter(a=>a.id!==button.dataset.referenceRemove);changed();render();});
  const inherit=root.querySelector('[data-reference-inherit]');if(inherit)inherit.onclick=()=>{const rows=c.extensions.filter(x=>!x.removed_at),previous=rows[rows.indexOf(e)-1];e.references=structuredClone(previous.references||[]);changed();render();};
  libraryButton.onclick=async()=>{
    try {
    const item=await pickLibraryAsset({title:'选择续接参考图片或声音'});if(!item||isDisposed())return;
    const media=item.snapshot.media.filter(m=>['image','audio'].includes(m.meta.kind));
    const dialog=scopedModal(`<h2>加入本段参考</h2>${media.length?field('素材文件',`<select data-reference-media>${opts(media.map(m=>[m.id,m.name||m.meta.kind]),media[0].id)}</select>`):'<p>所选版本没有图片或声音，请选择其他资产。</p>'}<p class="helper">仅引用所选固定版本，不导入资料PROMPT。</p><div class="dialog-actions"><button data-ref-cancel>取消</button>${media.length?'<button class="primary" data-ref-apply>加入本段</button>':''}</div>`);
    dialog.querySelector('[data-ref-cancel]').onclick=()=>dialog.close();
    const apply=dialog.querySelector('[data-ref-apply]');if(apply)apply.onclick=()=>{if(isDisposed())return;const selected=media.find(m=>m.id===dialog.querySelector('[data-reference-media]').value);dialog.close();action(async()=>{await save();await importFile({extension:e.id,reference:{asset:item.id,version:item.snapshot.id,media:selected.id}});});};
    } catch(error) {if(!isDisposed())await action(async()=>{throw error;});}
  };
}
