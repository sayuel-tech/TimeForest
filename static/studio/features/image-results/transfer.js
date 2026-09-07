import * as ui from '../../ui/primitives.js';
import {api} from '../../core/api-client.js';
import {libraryApi} from '../asset-picker/library-client.js';
import {selectionDialog} from '../asset-picker/project-use.js';

/** Reuse the exact video reference preview/apply UI and transaction service. */
export async function sendToVideo(asset,signal){
  const data=await api('/projects','GET',undefined,signal);
  const projects=data.projects.filter(p=>p.kind!=='image');
  if(!projects.length)throw new Error('请先创建一个视频项目，再从资产库引用这张图片。');
  const choice=await new Promise(resolve=>{
    const d=ui.modal(`<h2>用于视频项目</h2><p>下一步预览用途与影响，确认后才修改目标项目。</p>${ui.field('目标项目',`<select id="image-video-project">${ui.opts(projects.map(p=>[p.id,p.name]),projects[0].id)}</select>`)}<div class="dialog-actions"><button id="video-cancel">取消</button><button class="primary" id="video-next">下一步</button></div>`);
    d.oncancel=()=>resolve(null);d.querySelector('#video-cancel').onclick=()=>{d.close();resolve(null);};
    d.querySelector('#video-next').onclick=()=>{const id=d.querySelector('select').value;d.close();resolve(id);};
  });if(!choice||signal.aborted)return;
  const project=await api('/projects/'+choice,'GET',undefined,signal);
  if(!project.segments.length)throw new Error('目标项目尚无片段，请先准备视频时间线。');
  const segment=await new Promise(resolve=>{
    const d=ui.modal(`<h2>选择片段</h2>${ui.field('目标片段',`<select>${ui.opts(project.segments.map((s,i)=>[s.id,'P'+String(i+1).padStart(2,'0')]),project.segments[0].id)}</select>`)}<p>本次仅修改所选片段的引用；其他片段的继承按视频项目原设置处理。</p><div class="dialog-actions"><button id="segment-cancel">取消</button><button class="primary" id="segment-next">查看引用影响</button></div>`);
    d.oncancel=()=>resolve(null);d.querySelector('#segment-cancel').onclick=()=>{d.close();resolve(null);};d.querySelector('#segment-next').onclick=()=>{const id=d.querySelector('select').value;d.close();resolve(id);};
  });if(!segment||signal.aborted)return;
  const owner=crypto.randomUUID(),bundle=await libraryApi(`/assets/${asset.id}/bindings?version=${asset.version}&owner=${owner}`,'GET',undefined,signal);
  const shot=project.segments.find(s=>s.id===segment),prior=shot.resolved_assets||[];
  const session={controller:{signal},get disposed(){return signal.aborted;}};
  const result=await selectionDialog({project,session},bundle,prior,{
    asset:asset.id,version:asset.version,owner,segment,target:'references',revision:project.revision,subject:'1',replace:[],
    entries:Object.fromEntries(bundle.entries.map(e=>[e.key,{selected:e.selected,media:e.selected_media,purpose:e.purpose}])),
  });
  if(result&&!signal.aborted)ui.toast('图片已应用到所选视频项目');
}
