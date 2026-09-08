/** Read ownership, independent of mode payloads and generation state machines. */
export const readStamp = session => ({project:session.project, revision:session.project.revision,version:session.version});
export function uncertainMutation(session,error){
  if(session.disposed||!(error.kind==='network'||error.status>=500||error.status===200))return false;
  session.awaitingStatus=true;session.connection?.(error);return true;
}
export function requireKnownStatus(session){
  if(session.awaitingStatus)throw new Error('上次操作结果尚未确认，请先刷新状态或在任务列表核对，勿重复提交。');
}
export function currentRead(session, stamp, next) {
  return !session.disposed && !session.controller?.signal.aborted &&
    session.version===stamp.version &&
    session.project === stamp.project && next.id === session.project.id &&
    !(Number(next.revision) < Number(session.project.revision));
}
export function canReplaceDraft(session, root) {
  if(session.disposed || session.dirty || session.working || session.actionPending)return false;
  if(!root)return true;
  const doc=root.ownerDocument,active=doc.activeElement;
  return !doc.querySelector('dialog[open]') &&
    !(root.contains(active)&&active?.matches('input,textarea,select,[contenteditable="true"]')) &&
    ![...root.querySelectorAll('video,audio')].some(media=>!media.paused);
}
