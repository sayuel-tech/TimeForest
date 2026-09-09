import {esc} from './primitives.js';
import {runTiming,runStatusRow} from './run-timing.js';
export function creationJobStatus(job){
  if(!job)return '';
  return runStatusRow(`<div><strong>${esc(job.phase)}</strong>${job.error?`<p>${esc(job.error)}</p>`:''}</div>`,runTiming({start:job.created,end:job.updated,live:['queued','running','preparing','submitting','cancel_requested'].includes(job.state)}));
}
