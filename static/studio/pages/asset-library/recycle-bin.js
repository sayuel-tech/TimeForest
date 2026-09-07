import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import * as ui from '../../ui/primitives.js';
import {api} from '../../core/api-client.js';

export const recycleCategories=[['assets','资产库移除的'],['projects','项目移除的'],['generations','生成移除的']];
const modes={video_assembly:'视频接续',swap:'参考视频换人',image_story:'参考图长视频',text_story:'文生视频',image_assets:'图片资产创作',legacy:'旧版项目'};
const states={success:'已生成',complete:'已生成',failed:'失败',cancelled:'已取消'};
export function recycleUrl(category='assets',query='',page=1){
  const p=new URLSearchParams({view:'trash',recycle:category});
  if(query)p.set('q',query);if(page>1)p.set('page',page);
  return '#/assets?'+p;
}
export function restoreRequest(item){
  if(item.blocked_reason)throw new Error(item.blocked_reason);
  const revision=item.revision;
  if(['assembly_clip','assembly_extension','assembly_run'].includes(item.type))return {path:`/assembly/${item.project}/visibility`,body:{revision,id:item.id,kind:item.type.slice(9),removed:false}};
  if(item.type==='asset')return {path:`/library/assets/${item.id}/trash`,body:{revision,restore:true}};
  if(item.type==='project')return {path:`/projects/${item.id}/trash`,body:{revision,restore:true}};
  if(item.type==='image_task')return {path:`/image-projects/${item.project}/tasks/${item.id}/discard`,body:{revision,restore:true}};
  if(item.type==='legacy_project')return {path:`/legacy/${item.id}/trash`,body:{restore:true}};
  if(['image_run','video_run'].includes(item.type))return {path:`/projects/${item.project}/records/visibility`,body:{record:item.id,segment:item.segment,revision,removed:false}};
  throw new Error('不支持的恢复类型');
}
export function recycleView(data,query=''){
  const pages=Math.max(1,Math.ceil(data.total/data.limit));
  return `<section class="recycle-bin"><div class="recycle-heading"><h2>回收站</h2><p class="helper">按来源查看移除内容。恢复保留原文件和已有引用，不会重新生成或自动选用。</p></div><nav class="recycle-categories" aria-label="回收站分类">${recycleCategories.map(([key,label])=>`<a class="btn ${data.category===key?'active':''}" ${data.category===key?'aria-current="page"':''} href="${ui.esc(recycleUrl(key))}">${label}<span>${data.counts[key]??0}</span></a>`).join('')}</nav><form class="library-search"><input name="q" value="${ui.esc(query)}" aria-label="搜索移除内容" placeholder="搜索名称、任务或种子"><button>搜索</button><a href="${ui.esc(recycleUrl(data.category))}">清除搜索</a></form><div id="recycle-error" role="alert"></div>${data.category==='assets'&&data.items.length?'<div class="library-toolbar"><label><input type="checkbox" id="recycle-select-all"> 选择本页</label><button id="recycle-restore-selected" disabled>恢复选中资产</button></div>':''}<div class="recycle-list">${data.items.map((item,i)=>`<article class="recycle-item">${data.category==='assets'?`<input type="checkbox" data-recycle-select="${i}" aria-label="选择${ui.esc(item.title)}">`:''}${item.preview?`<img src="${ui.esc(item.preview)}" alt="${ui.esc(item.title)}" loading="lazy">`:'<span class="recycle-icon" aria-hidden="true">↶</span>'}<div class="recycle-copy"><h3>${ui.esc(item.title)}</h3><small>${ui.esc(modes[item.mode]||({image:'图片资产',video:'视频资产',audio:'声音资产',workflow:'工作流资料'}[item.kind])||'资产')}${item.task_name?' · '+ui.esc(item.task_name):''}${item.state?' · '+ui.esc(states[item.state]||item.state):''}</small>${item.type.endsWith('_run')?`<small>记录 ${ui.esc(item.id.slice(0,10))} · 种子 ${ui.esc(item.seed??'未记录')}</small>`:''}<small>移除时间：${ui.esc(item.removed_at?new Date(typeof item.removed_at==='number'?item.removed_at*1000:item.removed_at).toLocaleString():'未记录')}</small>${item.blocked_reason?`<p class="helper">${ui.esc(item.blocked_reason)}${item.parent_deleted?` · <a href="${ui.esc(recycleUrl('projects',item.title))}">前往项目回收站</a>`:''}</p>`:''}</div><div class="recycle-actions">${item.open_url&&(item.type==='asset'||item.type.endsWith('_run')&&!item.parent_deleted)?`<a href="${ui.esc(item.open_url)}">${item.type==='asset'?'查看资产':'打开所属项目'}</a>`:''}<button data-recycle-restore="${i}" ${item.blocked_reason?'disabled':''}>恢复</button></div></article>`).join('')||'<div class="panel empty"><h3>此分类暂无匹配的移除记录</h3><p>其他分类可在上方切换。</p></div>'}</div><div class="library-pagination">${data.page>1?`<a class="btn" href="${ui.esc(recycleUrl(data.category,query,data.page-1))}">上一页</a>`:''}<span>${data.total} 条 · ${data.page} / ${pages}</span>${data.page<pages?`<a class="btn" href="${ui.esc(recycleUrl(data.category,query,data.page+1))}">下一页</a>`:''}</div></section>`;
}

export async function mountRecycleBin(content,params,signal){
  const requested=params.get('recycle')||'assets';
  const category=recycleCategories.some(([key])=>key===requested)?requested:'assets',query=params.get('q')||'';
  let pending=false,load=0;
  async function render(){
    const ticket=++load;
    try{
      const args=new URLSearchParams({category,q:query,page:params.get('page')||'1'});
      const data=await api('/recycle-bin?'+args,'GET',undefined,signal);
      if(signal.aborted||ticket!==load)return;
      content.innerHTML=recycleView(data,query);
      content.querySelector('form').onsubmit=e=>{e.preventDefault();location.hash=recycleUrl(category,new FormData(e.target).get('q'));};
      const selected=()=>[...content.querySelectorAll('[data-recycle-select]:checked')].map(b=>data.items[Number(b.dataset.recycleSelect)]);
      const batch=content.querySelector('#recycle-restore-selected');
      if(batch){
        const update=()=>batch.disabled=pending||!selected().length;
        content.querySelectorAll('[data-recycle-select]').forEach(b=>b.onchange=update);
        content.querySelector('#recycle-select-all').onchange=e=>{content.querySelectorAll('[data-recycle-select]').forEach(b=>b.checked=e.target.checked);update();};
        batch.onclick=async()=>{
          if(pending||signal.aborted)return;
          const items=selected();if(!items.length)return;pending=true;let restored=0,attempted=false;
          try{
            if(!await ui.confirm('恢复选中的 '+items.length+' 项资产？','恢复到资产库原列表，现有项目引用和资产版本保留。','恢复'))return;
            if(signal.aborted)return;attempted=true;
            content.querySelectorAll('button').forEach(b=>b.disabled=true);
            for(const item of items){
              if(signal.aborted)return;
              const request=restoreRequest(item);await api(request.path,'POST',request.body,signal);restored++;
            }
            if(!signal.aborted)ui.toast('已恢复 '+restored+' 项资产');
          }catch(error){if(!signal.aborted)ui.toast('已恢复 '+restored+' 项，其余未恢复：'+error.message);}
          finally{pending=false;if(!signal.aborted){if(attempted)await render();else update();}}
        };
      }
      content.querySelectorAll('[data-recycle-restore]').forEach(button=>button.onclick=async()=>{
        if(pending||signal.aborted)return;pending=true;
        try{
          const item=data.items[Number(button.dataset.recycleRestore)];
          if(!await ui.confirm('恢复「'+item.title+'」？','将恢复到原来的列表。生成记录不会自动选用；恢复项目不会恢复其中另行移除的生成记录。','恢复'))return;
          if(signal.aborted)return;
          content.querySelectorAll('[data-recycle-restore]').forEach(b=>b.disabled=true);
          const request=restoreRequest(item);
          await api(request.path,'POST',request.body,signal);
          if(signal.aborted)return;
          ui.toast('已恢复，可回到原列表查看');await render();
        }catch(error){
          if(!signal.aborted){content.querySelector('#recycle-error').innerHTML=`<div class="notice error">${errorFeedback(error)}</div><button id="recycle-reload">刷新回收站</button>`;bindErrorFeedback(content.querySelector('#recycle-error'));content.querySelector('#recycle-reload').onclick=render;}
        }finally{
          pending=false;
          if(!signal.aborted&&ticket===load)content.querySelectorAll('[data-recycle-restore]').forEach(b=>b.disabled=Boolean(data.items[Number(b.dataset.recycleRestore)]?.blocked_reason));
        }
      });
    }catch(error){if(!signal.aborted){
      const message=error.status===404?'当前网站后台尚未提供分类回收站，请保存编辑并重启导演台后刷新。':error.message;
      content.innerHTML=`<div class="notice error">${errorFeedback({kind:error.kind,message,raw:error.raw??error.message})}</div>`;
      bindErrorFeedback(content);
    }}
  }
  await render();
}
