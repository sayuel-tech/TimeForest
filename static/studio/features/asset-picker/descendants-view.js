import {assetVersionLink,projectOriginLink} from '../../ui/asset-origin.js';
import {esc} from '../../ui/primitives.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {libraryApi} from './library-client.js';

/** Only scan when requested; page within one captured database upper bound. */
export function mountAssetDescendants(slot,ref,signal,{projectResults=false}={}){
  const details=document.createElement('details');
  details.className='asset-lineage';
  details.dataset.descendantScope=projectResults?'projects':'library';
  details.innerHTML=`<summary>${projectResults?'查看项目中的生成结果（含未入库）':'查看已入库的下游结果'}</summary><p class="helper">${projectResults?'包含历史编排和已移除记录':'包括固定历史版本'}；按制作来源查找，不把历史使用登记当作派生关系。${projectResults?'按保存的生成记录查找，是否入库由资产库记录另行展示。':'这里只列已入库的媒体版本。'}缺少身份的旧记录及外部包关系不保证覆盖。</p><div data-descendant-status role="status"></div><ol data-descendant-results></ol><div data-descendant-error></div><button type="button" data-descendant-more>查找下游结果</button>`;
  slot.append(details);
  const status=details.querySelector('[data-descendant-status]'),list=details.querySelector('[data-descendant-results]'),errorSlot=details.querySelector('[data-descendant-error]'),button=details.querySelector('button');
  let started=false,busy=false,cursor=projectResults?'0:0:':'0:0',upper=null,scanned=0,unknown=0,count=0;
  const load=async()=>{
    if(busy||cursor===null||signal?.aborted||!details.isConnected)return;
    busy=true;started=true;button.disabled=true;status.textContent='正在读取下一批来源记录…';errorSlot.innerHTML='';
    try{
      const q=new URLSearchParams({version:ref.version,media:ref.media,cursor,...(upper===null?{}:projectResults?{before:upper}:{upper})});
      const data=await libraryApi(`/assets/${encodeURIComponent(ref.asset)}/${projectResults?'generation-descendants':'descendants'}?${q}`,'GET',undefined,signal);
      if(signal?.aborted||!details.isConnected)return;
      if(data.version!==1)throw Error('当前后台未提供下游追溯，请在保存编辑并结束任务后重启导演台。');
      cursor=data.cursor;upper=projectResults?data.before:data.upper;scanned+=data.scanned;unknown+=data.incomplete;count+=data.rows.length;
      list.insertAdjacentHTML('beforeend',data.rows.map(r=>`<li>${projectResults?projectOriginLink(r.project)+' · '+esc(r.name):assetVersionLink(r,r.name)}${r.historical?(projectResults?' · 历史编排':' · 历史版本'):''}${r.removed?' · 已移除':''}<p class="helper">${projectResults?'生成记录 '+esc(r.output||r.run):'固定版本 '+esc(r.version)}</p></li>`).join(''));
      status.textContent=`已读取 ${scanned} 项${projectResults?'生成结果':'媒体版本'}，找到 ${count} 项已记录下游。${cursor===null?'本次范围已读取完毕。':'还有记录可继续查找。'}${unknown?`其中 ${unknown} 项来源不完整或无法继续核对，结果可能不完整。`:''}`;
      button.hidden=cursor===null;button.textContent='继续查找';
    }catch(error){
      if(signal?.aborted||!details.isConnected)return;
      status.textContent='读取未完成，已有结果保留。';errorSlot.innerHTML=errorFeedback(error);bindErrorFeedback(errorSlot);button.textContent='重新读取这一批';
    }finally{busy=false;if(details.isConnected)button.disabled=false;}
  };
  details.ontoggle=()=>{if(details.open&&!started)void load();};
  button.onclick=()=>void load();
}
