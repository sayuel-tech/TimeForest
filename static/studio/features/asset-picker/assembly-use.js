import {referencePurposes,referenceMetadata,needsSubject} from '../../ui/reference-metadata.js';
import * as ui from '../../ui/primitives.js';
import {api} from '../../core/api-client.js';
import {imageDestinations} from './destinations.js';

/** Transfer only to an explicit existing extension; no generation or hidden task creation. */
export async function useImageInAssembly(asset,project,signal){
  const targets=imageDestinations(project),images=asset.snapshot.media.filter(m=>m.meta.kind==='image');
  if(!targets.length)throw new Error('目标项目尚无可用续写段，请先在视频接续中添加续接，再使用这张图片。');
  if(!images.length)throw new Error('所选资产版本没有图片。');
  if(project.library_usage_version!==1)throw new Error('当前后台未加载跨模式资产引用更新，请重启导演台后重试。');
  return new Promise(resolve=>{
    const d=ui.scopedModal(`<h2>用于视频接续</h2>${ui.field('目标续写段',`<select data-use-extension>${ui.opts(targets.map(t=>[t.id,t.label]),targets[0].id)}</select>`)}${ui.field('图片',`<select data-use-media>${ui.opts(images.map(m=>[m.id,m.name||'图片']),images.find(m=>m.role==='primary')?.id||images[0].id)}</select>`)}${ui.field('素材用途',`<select data-use-purpose>${ui.opts(referencePurposes('image'),'character')}</select>`)}${ui.field('角色编号','<input data-use-subject type="number" min="1" max="99" value="1">')}<p class="helper">加入所选续写段的参考素材，保留原视频、描述、参数与已有候选；不会自动生成，也不会导入资产资料正文。</p><p data-use-error role="alert"></p><div class="dialog-actions"><button data-use-cancel>取消</button><button class="primary" data-use-apply>确认加入</button></div>`);
    const purpose=d.querySelector('[data-use-purpose]'),subject=d.querySelector('[data-use-subject]');
    purpose.onchange=()=>{subject.disabled=!needsSubject(purpose.value);};
    let sending=false,finished=false,committed=false;
    const finish=value=>{if(finished)return;finished=true;signal?.removeEventListener('abort',abort);d.removeEventListener('close',closed);resolve(value);};
    const abort=()=>{d.close();finish(null);};
    const closed=()=>{if(!d.open)finish(null);};
    signal?.addEventListener('abort',abort,{once:true});
    d.oncancel=()=>finish(null);d.addEventListener('close',closed);
    d.querySelector('[data-use-cancel]').onclick=()=>{d.close();finish(null);};
    d.querySelector('[data-use-apply]').onclick=async()=>{
      if(sending||signal?.aborted||finished||committed)return;
      const button=d.querySelector('[data-use-apply]');sending=true;button.disabled=true;
      try{
        await api('/assembly/'+project.id+'/references','POST',{
          revision:project.revision,extension:d.querySelector('[data-use-extension]').value,
          reference:{asset:asset.id,version:asset.version,media:d.querySelector('[data-use-media]').value},
          ...referenceMetadata('image',purpose.value,subject.value),
        },signal);
        finish(true);d.close();
      }catch(error){committed=error.code==='LIBRARY_USAGE_PENDING';if(d.open)d.querySelector('[data-use-error]').textContent=error.message;}
      finally{sending=false;if(d.open)button.disabled=committed;}
    };
    if(signal?.aborted)abort();
  });
}
