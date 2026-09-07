import {esc,elapsed} from './primitives.js';

const timestamp=value=>Number.isFinite(Number(value))&&Number(value)>0?Number(value):null;

// Presentation only. Each feature supplies its own persisted timing semantics.
export function runTiming({start,end,live=false,label='本次任务用时',queuedAt,uncertain=false}={}) {
  start=timestamp(start);end=timestamp(end);queuedAt=timestamp(queuedAt);
  if(uncertain)return '<small class="run-timing">用时待确认</small>';
  if(!start||(!live&&!end))return '<small class="run-timing">用时未记录</small>';
  return `<div class="run-timing"><small>${esc(label)}</small><strong class="run-clock" data-clock="${start}" ${!live&&end?`data-clock-end="${end}"`:''}>${elapsed(start,live?null:end)}</strong>${queuedAt?`<small>排队用时 ${elapsed(queuedAt,start)}</small>`:''}</div>`;
}

// statusHtml is rendered/escaped by the calling feature, including its own actions.
export function runStatusRow(statusHtml,timingHtml) {
  return `<div class="row between run-status-row">${statusHtml}${timingHtml}</div>`;
}
