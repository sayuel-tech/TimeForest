import {api} from '../../core/api-client.js';
import * as ui from '../../ui/primitives.js';
import {openProductionSettings,parameterGrid,productionSettingsActions,productionSettingsMarkup,productionGroups,parameterField,seedFields,bindSettingsNavigation,parameterLoras,validateSettingsInputs} from '../../ui/production-settings.js';

export function visibleParameters(catalog,extension) {
  if(!extension)return [];
  const values=extension.configurations[extension.recipe];
  return catalog.recipes.find(r=>r.id===extension.recipe).parameters.filter(f=>!f.when||Object.entries(f.when).every(([k,v])=>values[k]===v));
}
export function resetParameters(extension,catalog) {
  const next=structuredClone(extension);
  next.configurations[next.recipe]=structuredClone(catalog.defaults[next.recipe]);
  next.seed_mode='random';next.seed='0';next.sound='native';
  return next;
}
export function switchRecipe(extension,recipe) {
  if(!extension.configurations[recipe])throw new Error('缺少对应工作流草稿');
  return {...extension,recipe};
}
const choices={reference_size:[['match','匹配画布'],['max','原参考细节（更耗显存）']],size_mode:[['area','面积＋比例'],['custom','自定义宽高']],aspect:['9:16','16:9','1:1','4:3','3:4']};
export async function settingsDialog({catalog,extension,output,onApply,isDisposed,signal,lastSeed}) {
  let e=extension?structuredClone(extension):null,o=structuredClone(output),section=e?'core':'export';
  const surface=openProductionSettings({signal});
  const {dialog,content,closed}=surface;
  function draw(){
    if(isDisposed()||!dialog.open||!content.isConnected)return;
    const config=e?.configurations[e.recipe];
    const field=f=>{
      const list={model:'models',lora:'loras',vae:'vaes',clip:'clips',sampler:'samplers',scheduler:'schedulers'}[f.type];
      const model=['model','lora','vae','clip'].includes(f.type);
      return parameterField({...f,type:model?'model':f.type},config[f.key],{attributes:`data-param="${ui.esc(f.key)}"`,options:list?catalog[list]:choices[f.key],preserveCurrent:true});
    };
    const fields=visibleParameters(catalog,e),sections=[];
    if(e){
      for(const [key,title] of Object.entries(productionGroups)){
        let html=fields.filter(f=>f.group===key).map(field).join('');
        if(key==='core')html=ui.field('工作流',`<select data-recipe>${ui.opts(catalog.recipes.map(r=>[r.id,r.name]),e.recipe)}</select>`)+html;
        if(key==='sampling')html+=seedFields({mode:e.seed_mode,value:e.seed,lastSeed});
        if(key==='assets')html+=ui.field('续接声音',`<select data-sound>${ui.opts([['native','生成声音'],['mute','续接静音']],e.sound)}</select>`,'不改变原片声音；无声原片使用明确的静音上下文。');
        if(key==='lora'&&e.recipe==='dance_split')html+=parameterLoras(config.loras,catalog.loras,{keyAttribute:'data-part'});
        if(html)sections.push({key,title,html:key==='lora'?html:parameterGrid(html)});
      }
    }
    sections.push({key:'export',title:'项目导出规格',html:`<p>仅影响拼接副本；默认等比例补边，原件保留。</p>${['width','height'].map(k=>ui.field(k==='width'?'成片宽度（px）':'成片高度（px）',`<input type="number" min="2" max="8192" step="2" data-output="${k}" value="${o[k]}">`)).join('')}${ui.field('导出帧率',`<select data-output="fps">${ui.opts([24,25,30,50,60],o.fps)}</select>`)}${ui.field('尺寸适配',`<select data-output="fit">${ui.opts([['contain','等比例补边'],['cover','填满画布（裁切）']],o.fit)}</select>`)}`});
    content.innerHTML=productionSettingsMarkup({scope:e?'当前续写段参数；导出规格作用于整个拼接项目':'当前项目导出规格（未选择续写段）',
      directory:e?'<p class="helper">来源：当前网站工作流目录；本地文件刷新不会连接生成引擎。</p><button data-refresh>刷新本地模型列表</button>':'',sections,
      actions:productionSettingsActions([...(e?[{role:"reset",label:"恢复默认",attributes:"data-reset"}]:[]),{role:"cancel",label:"取消",attributes:"data-cancel"},{role:"apply",label:"应用",attributes:"data-apply"},{role:"save",label:"保存",attributes:"data-save",primary:true}]),footer:'应用到当前续写段与项目导出草稿；保存会持久化当前项目的全部草稿。恢复默认仅重置当前续写参数，不改变项目导出规格。'});
    bindSettingsNavigation(content,section,key=>section=key);

    dialog.querySelectorAll('[data-param]').forEach(input=>input.onchange=()=>{const key=input.dataset.param;config[key]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;if(catalog.recipes.find(r=>r.id===e.recipe).parameters.some(f=>f.when&&Object.hasOwn(f.when,key)))draw();});
    dialog.querySelectorAll('[data-lora]').forEach(input=>input.onchange=()=>{config.loras[Number(input.dataset.lora)][input.dataset.part]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;});
    dialog.querySelectorAll('[data-output]').forEach(input=>input.onchange=()=>o[input.dataset.output]=input.dataset.output==='fit'?input.value:Number(input.value));
    const bind=(selector,fn)=>{const el=dialog.querySelector(selector);if(el)el.onchange=fn;};
    bind('[data-recipe]',event=>{e=switchRecipe(e,event.target.value);draw();});
    bind('[data-seed-mode]',event=>{e.seed_mode=event.target.value;draw();});
    bind('[data-seed]',event=>e.seed=event.target.value);
    bind('[data-sound]',event=>e.sound=event.target.value);
    dialog.querySelector('[data-cancel]').onclick=surface.cancel;
    const apply=save=>surface.run(async()=>{if(isDisposed())return false;await onApply(e,o,save);ui.toast(save?'草稿已保存':'已应用到草稿，尚未保存');return true;},{closeOnSuccess:true,validate:()=>validateSettingsInputs(content)});
    dialog.querySelector('[data-apply]').onclick=()=>apply(false);
    dialog.querySelector('[data-save]').onclick=()=>apply(true);
    const reset=dialog.querySelector('[data-reset]');if(reset)reset.onclick=()=>surface.run(()=>{e=resetParameters(e,catalog);draw();});
    const refresh=dialog.querySelector('[data-refresh]');if(refresh)refresh.onclick=()=>surface.run(async()=>{const next=await api('/assembly/catalog/refresh','POST',{},signal);if(!isDisposed()&&surface.alive()){catalog=next;draw();}});
  }
  draw();
  await closed;
}
