import {addRecordButton} from '../prompt-library/records.js';
import {assetOriginMarkup} from '../../ui/asset-origin.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {libraryApi} from './library-client.js';
import {mountAssetDescendants} from './descendants-view.js';
/** Capture this exact slot: late responses cannot overwrite another asset or draft. */
export async function mountAssetOrigin(slot,ref,signal){
  if(!slot)return;
  slot.innerHTML='<p class="helper" role="status">正在读取固定版本来源…</p>';
  try{
    if(ref.supported===false)throw new Error('当前网站未加载资产来源功能，请在任务结束并保存编辑后重启导演台。');
    const q=new URLSearchParams({version:ref.version,media:ref.media});
    const data=await libraryApi(`/assets/${encodeURIComponent(ref.asset)}/origin?${q}`,'GET',undefined,signal);
    if(signal?.aborted||!slot.isConnected)return;
    if(data.version!==1)throw new Error('当前网站未加载资产来源功能，请在任务结束并保存编辑后重启导演台。');
    slot.innerHTML=assetOriginMarkup(data);
    const anchor=document.createElement('span');slot.append(anchor);addRecordButton(anchor,{path:'/asset-records/'+encodeURIComponent(ref.asset)+'?'+q,signal});
    if(data.lineage?.version===1)mountAssetDescendants(slot,ref,signal);
    if(data.generation_descendants_version===1)mountAssetDescendants(slot,ref,signal,{projectResults:true});
    else if(data.lineage?.version===1){
      const notice=document.createElement('p');notice.className='helper';
      notice.textContent='当前后台尚未加载项目生成结果追溯，请在保存编辑并结束任务后重启导演台。';slot.append(notice);
    }
  }catch(error){
    if(signal?.aborted||!slot.isConnected)return;
    slot.innerHTML=errorFeedback(error)+'<button type="button" data-origin-retry>重新读取来源</button>';
    bindErrorFeedback(slot);
    slot.querySelector('[data-origin-retry]').onclick=()=>mountAssetOrigin(slot,ref,signal);
  }
}
