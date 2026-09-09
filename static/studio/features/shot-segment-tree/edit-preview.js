import {scopedModal,esc} from '../../ui/primitives.js';
import {mediaPlayer,bindMediaPlayers} from '../../ui/media-player.js';

// Preview the saved edit decisions without rendering a new composite or invoking a model.
export function previewEdit(items,url,signal){
  if(!items.length)throw Error('没有纳入成片的片段');
  const dialog=scopedModal(`<h2>连续预览</h2><p data-preview-label></p>${mediaPlayer(url(items[0]),'时间轴连续预览')}<div class="dialog-actions"><button data-close>关闭</button></div>`),video=dialog.querySelector('video');
  const unbind=bindMediaPlayers(dialog);let index=0,changing=false;
  const show=()=>{const item=items[index];changing=true;dialog.querySelector('[data-preview-label]').textContent=`片段 ${index+1} / ${items.length} · 按当前剪辑区间播放`;video.src=url(item);video.load();};
  video.addEventListener('loadedmetadata',()=>{video.currentTime=items[index].range.in_ms/1000;changing=false;video.play().catch(()=>{});});
  const next=()=>{if(changing)return;if(index+1>=items.length){video.pause();return;}index++;show();};
  video.addEventListener('timeupdate',()=>{if(video.currentTime>=items[index].range.out_ms/1000-.015)next();});video.addEventListener('ended',next);
  const close=()=>{video.pause();unbind();dialog.close();};dialog.querySelector('[data-close]').onclick=close;dialog.addEventListener('close',()=>{video.pause();unbind();});signal?.addEventListener('abort',close,{once:true});show();
}
