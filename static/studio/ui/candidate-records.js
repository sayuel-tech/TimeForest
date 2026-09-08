import {esc} from './primitives.js';

export function recordControl(record,{selected=false,busy=false,image=false,assembly=false}={}) {
  const restore=assembly?'data-restore-run':'data-record-restore',remove=assembly?'data-remove-run':'data-record-remove';
  if(record.removed_at)return `<button type="button" class="quiet" ${restore}="${esc(record.id)}" ${busy?'disabled':''}>恢复</button>`;
  if(selected)return '<small>当前已选用，换选后可移除</small>';
  const ended=(image||assembly?['success','failed','cancelled']:['complete','failed']).includes(record.state||record.status);
  if(!ended)return '<small>运行中或待确认，暂不可移除</small>';
  return `<button type="button" class="quiet" ${remove}="${esc(record.id)}" ${busy?'disabled':''}>移除</button>`;
}

export function removedRecords(records,{busy=false,preview=()=>'',assembly=false}={}) {
  const removed=records.filter(r=>r.removed_at);
  if(!removed.length)return '';
  return `<details class="removed-records"><summary>已移除（${removed.length}）</summary><p class="helper">已从候选列表移除。原文件、资产和已有引用保留，可恢复。<a href="#/assets?view=trash&recycle=generations">前往回收站查看全部</a></p>${removed.map(r=>`<div class="candidate-record row between">${preview(r)}<small>${esc(r.id.slice(0,8))} · 种子 ${esc(r.seed??'未记录')}</small>${recordControl(r,{busy,assembly})}</div>`).join('')}</details>`;
}

export function recordConfirmation(restore) {
  return restore?'恢复后会重新出现在候选或运行记录列表，不会自动选用或重新生成。':'从候选和日常运行记录中移除，可在“已移除”中恢复。原文件、已入库资产和已有引用保留；此操作不释放磁盘空间。';
}
