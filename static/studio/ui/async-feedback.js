import {errorFeedback,bindErrorFeedback} from './error-feedback.js';
import {esc} from './primitives.js';

/** A stable status slot; transport failure never means the server task stopped. */
export function asyncFeedback(root, signal) {
  let connection=null,transfer=null;
  function render(){
    if(signal?.aborted)return;
    let box=root.querySelector('[data-async-feedback]');
    if(!box&&!connection&&!transfer)return;
    if(!box){box=root.ownerDocument.createElement('div');box.dataset.asyncFeedback='';
      const anchor=root.querySelector('.steps');anchor?anchor.after(box):root.prepend(box);}
    box.hidden=!connection&&!transfer;
    box.innerHTML=transfer?`<p class="notice" role="status">${esc(transfer)}</p>`:connection?errorFeedback({kind:'network',message:'状态连接中断，正在重新读取；显示的是最后已知状态，请勿重复提交。',raw:connection.raw??connection.message}):'';
    if(connection&&!transfer)bindErrorFeedback(box);
  }
  return {render,connection(error){connection=error;render();},transfer(info){transfer=info?info.phase+(info.phase==='正在上传文件'&&info.total?' · '+Math.floor(info.loaded/info.total*100)+'%':''):null;render();}};
}
