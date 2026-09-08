import {promptApi} from './api.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';

/** Separate receipt status: retry only the saved snapshot, never a project write. */
export function promptCollectionNotice(root,session){
  if(!root||session.disposed)return;
  let box=root.querySelector('[data-prompt-collection]');
  if(!box){box=document.createElement('div');box.className='notice prompt-notice';box.dataset.promptCollection='1';root.prepend(box);}
  const pid=session.project.id;
  const show=async()=>{
    try{
      const data=await promptApi('/pending/'+pid,'GET',undefined,session.controller.signal);if(!box.isConnected||session.disposed)return;
      const transient=session.project.prompt_collection;
      if(!data.items.length){box.innerHTML=transient?.state==='pending'&&!transient.retryable?'<p>项目已保存，但提示词库及补记凭据写入失败。请保留本次文字，检查存储后另存到提示词库。</p>':'';return;}
      box.innerHTML='<p>项目已保存，有提示词尚未收录。</p><button data-retry-prompts>补记已保存提示词</button><div data-error></div>';
      box.querySelector('button').onclick=async e=>{e.target.disabled=true;try{for(const row of data.items)await promptApi('/receipts/'+row.receipt+'/retry','POST',{},session.controller.signal);await show();}catch(error){if(box.isConnected){const slot=box.querySelector('[data-error]');slot.innerHTML=errorFeedback(error);bindErrorFeedback(slot);}}finally{if(e.target.isConnected)e.target.disabled=false;}};
    }catch(e){if(!session.disposed&&box.isConnected){box.innerHTML='<p>提示词收录状态暂时无法读取；原项目保存状态不受影响。</p>'+errorFeedback(e);bindErrorFeedback(box);}}
  };
  void show();
}
