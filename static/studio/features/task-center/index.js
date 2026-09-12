import {updateStatusRegion} from '../../ui/status-region.js';
import {TASK_STATES as states} from '../../core/task-state.js';
import {api} from '../../core/api-client.js';
import {esc} from '../../ui/primitives.js';
import {errorFeedback, bindErrorFeedback} from '../../ui/error-feedback.js';

const actions={recover:'查询恢复',cancel:'取消排队',pause:'停止后续执行',stop:'停止当前生成',close:'结束等待并保留记录'};

export function confirmation(task,action) {
  if(task.kind==='creation'&&action==='recover')return '仅查询并接收原引擎编号对应的结果，不重新提交，不更换上游或当前参数。';
  if(task.kind==='creation'&&action==='close')return '结束这条本地记录的等待，保留原请求、编号和快照。不能证明远端请求已停止，远端可能仍在执行；网站不会自动重试。';
  if(task.kind==='creation'&&task.creation_mode==='authoring')return '停止接收这条写作请求。当前剧本与候选保留；云端已经开始的请求可能仍执行并计费。';
  if(task.kind==='assembly'&&action==='recover')return `查询「${task.name}」原提交并继续剩余续接任务，已登记的提交不会重复发送。`;
  if(task.kind==='assembly'&&action==='stop')return `停止「${task.name}」当前处理及后续任务？只控制本任务的引擎提交或媒体子进程，原件及已完成结果保留。`;
  if(action==='close')return `结束「${task.name}」这条旧提交的等待？系统会先重查引擎队列和历史。若仍无记录，保留原编号与快照并解除占用；其他排队任务随后可以继续。原提交的结果仍记为未确认，不会重新提交。`;
  if(action==='stop')return `停止「${task.name}」当前生成？只请求中断这条任务，已完成结果保留。${task.kind==='video'?'本项目后续任务也会停止。':''}通道会在引擎确认后释放；若引擎不支持按任务停止，会显示实际错误。`;
  if(action==='pause')return `停止「${task.name}」后续执行？当前内部生成任务会完成并保留结果，不再开始下一项。`;
  return `取消「${task.name}」这条排队任务？素材、参数和历史记录保留。已经开始的任务不会按排队取消。`;
}

export function visibleTasks(tasks,filter) {
  return tasks.filter(t=>t.active&&(filter!=='attention'||t.attention));
}

export function taskCard(task,index) {
  const progress=Number.isFinite(task.progress)?`<progress max="1" value="${Math.max(0,Math.min(1,task.progress))}" aria-label="任务进度"></progress>`:'';
  return `<article class="task-card ${task.attention?'needs-attention':''}" data-task-row="${index}" data-view-key="${esc(task.kind+':'+task.project+':'+task.id)}">
    <div class="task-card-heading"><div><small>${esc(task.kind==='image'?'图片资产创作':task.kind==='video'?'视频制作':task.kind==='assembly'?'视频接续':task.kind==='creation'?(task.creation_mode==='movie'?'电影创作':'剧本创作'):'本地处理')}</small><h3>${esc(task.name)}</h3></div><span class="badge">${esc(task.stop_requested&&task.active?'停止已请求':states[task.state]||task.state)}</span></div>
    <p>${esc(task.title)} <small>· ${esc(task.id.slice(0,8))}</small></p>
    <p class="task-note">${esc(task.note||'任务记录已保留')}</p>${progress}
    ${task.seed!==undefined&&task.seed!==null?`<small>种子 ${esc(task.seed)}</small>`:''}
    ${task.blocked_by?.length?`<div class="task-blockers">通道占用：${task.blocked_by.map(b=>`<a href="${esc(b.url)}" data-task-link>${esc(b.name)} · ${esc(b.id.slice(0,8))}</a>`).join('、')}</div>`:''}
    ${task.error_raw?`<details><summary>查看原始反馈</summary><pre>${esc(typeof task.error_raw==='string'?task.error_raw:JSON.stringify(task.error_raw,null,2))}</pre></details>`:''}
    <div class="task-actions"><a class="btn" data-task-link href="${esc(task.url)}">打开${task.kind==='local'?'资产任务':'项目'}</a>${task.actions.map(a=>`<button type="button" data-task-action="${a}" data-task-index="${index}">${task.kind==='assembly'&&a==='stop'?'停止当前任务':actions[a]}</button>`).join('')}</div>
    ${task.kind==='local'&&task.state==='running'?'<small>文件处理已开始，将完成当前操作；原件保留。</small>':''}
  </article>`;
}

/** Mounted once, outside route lifetimes and the workspace draft dialog. */
export function mountTaskCenter() {
  const button=document.querySelector('#global-tasks');
  if(!button)return;
  const dialog=document.createElement('dialog');dialog.id='task-center';dialog.setAttribute('aria-labelledby','task-center-title');
  dialog.innerHTML=`<div class="task-center-heading"><div><span class="eyebrow">TASK QUEUE</span><h2 id="task-center-title">当前任务队列</h2><p>跨页面管理正在执行与排队的项目，结束后自动移出。</p></div><button type="button" class="dialog-close" data-close aria-label="关闭任务列表">×</button></div>
    <div class="task-toolbar"><label>显示 <select data-filter><option value="active">当前队列</option><option value="attention">待确认占用</option></select></label><button type="button" data-refresh>刷新</button><small data-summary role="status"></small></div>
    <div data-task-error role="alert"></div><div data-task-confirm hidden></div><div data-task-list></div><small data-history></small>`;
  document.body.append(dialog);
  let disposed=false,readSerial=0;const controller=new AbortController();
  let tasks=[],renderedTasks=[],filter='active',pending=null,busy=false,loading=false,last='',opener=null;
  const list=dialog.querySelector('[data-task-list]'),error=dialog.querySelector('[data-task-error]'),confirm=dialog.querySelector('[data-task-confirm]');
  function render(){
    const rows=visibleTasks(tasks,filter);const html=rows.map(t=>taskCard(t,tasks.indexOf(t))).join('')||'<div class="task-empty">此处暂无任务</div>';
    if(html!==last){updateStatusRegion(list,html);last=html;}
    renderedTasks=tasks.slice();
  }
  function lock(value){
    list.inert=value;dialog.querySelector('[data-filter]').disabled=value;dialog.querySelector('[data-refresh]').disabled=value;
  }
  async function refresh(manual=false){
    if(disposed||loading||pending||busy)return;
    const serial=++readSerial;
    loading=true;
    try{
      const data=await api('/tasks','GET',undefined,controller.signal);
      if(disposed||serial!==readSerial||busy||pending)return;
      if(data.version!==1||!Array.isArray(data.tasks))throw new Error('任务列表后台尚未更新，请重启时间森林网站后刷新。');
      tasks=data.tasks;
      button.textContent=`任务列表${data.active_count?' · '+data.active_count:''}`;
      button.classList.toggle('has-attention',data.attention_count>0);
      button.title=data.attention_count?`${data.attention_count} 项需要处理`:'查看正在执行和排队的项目';
      dialog.querySelector('[data-summary]').textContent=`${data.active_count} 项进行中 · ${data.attention_count} 项需要处理`;
      dialog.querySelector('[data-history]').textContent='完成、失败或取消后自动移出队列。历史记录仍在各项目与资产库中保留。';
      if(manual)error.innerHTML='';
      // Do not replace controls while the user has keyboard focus within a row.
      if(dialog.open&&!pending&&!busy&&(manual||!list.contains(document.activeElement)))render();
    }catch(e){
      if(disposed||serial!==readSerial||e.name==="AbortError")return;
      if(e.status===404)e=new Error('任务列表后台尚未更新，请重启时间森林网站后刷新。');
      button.textContent='任务列表 · 连接待检查';
      if(dialog.open){error.innerHTML=errorFeedback(e);bindErrorFeedback(error);}
    }finally{loading=false;}
  }
  function clearConfirmation(){pending=null;confirm.hidden=true;confirm.innerHTML='';lock(false);}
  button.onclick=()=>{opener=document.activeElement;dialog.showModal();render();refresh(true);};
  dialog.querySelector('[data-close]').onclick=()=>{if(!busy)dialog.close();};
  dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
  dialog.addEventListener('close',()=>{clearConfirmation();opener?.focus();});
  dialog.querySelector('[data-filter]').onchange=e=>{filter=e.target.value;render();};
  dialog.querySelector('[data-refresh]').onclick=()=>refresh(true);
  dialog.addEventListener('click',async e=>{
    if(e.target.closest('[data-task-link]')){if(busy||pending){e.preventDefault();return;}dialog.close();return;}
    const action=e.target.closest('[data-task-action]');
    if(action&&!pending&&!busy){
      readSerial++;
      pending={task:renderedTasks[Number(action.dataset.taskIndex)],action:action.dataset.taskAction};
      confirm.innerHTML=`<h3>${esc(pending.task.name)}</h3><p class="helper">${esc(pending.task.title)} · ${esc(pending.task.id.slice(0,8))}</p><p>${esc(confirmation(pending.task,pending.action))}</p><div class="task-actions"><button type="button" data-no>返回</button><button type="button" class="primary" data-yes>确认${actions[pending.action]}</button></div>`;
      confirm.hidden=false;lock(true);confirm.querySelector('[data-no]').focus();
    }
    if(e.target.closest('[data-no]')&&!busy){clearConfirmation();dialog.querySelector('[data-filter]').focus();}
    if(e.target.closest('[data-yes]')&&pending&&!busy){
      if(disposed)return;
      busy=true;readSerial++;confirm.querySelectorAll('button').forEach(b=>b.disabled=true);
      try{
        const {task,action}=pending;
        const result=await api('/tasks/action','POST',{kind:task.kind,id:task.id,project:task.project,action,confirmed:true},controller.signal);
        if(disposed)return;
        error.innerHTML=`<p class="notice" role="status">${esc(result.message)}</p>`;
      }catch(err){if(disposed)return;error.innerHTML=errorFeedback(err);bindErrorFeedback(error);}
      finally{busy=false;if(disposed)return;clearConfirmation();await refresh();dialog.querySelector('[data-refresh]').focus();}
    }
  });
  refresh();
  const timer=setInterval(()=>{if(!document.hidden)refresh();},5000);
  return ()=>{disposed=true;readSerial++;controller.abort();clearInterval(timer);dialog.remove();button.onclick=null;};
}
