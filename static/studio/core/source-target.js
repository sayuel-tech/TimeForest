/** Resolve an immutable origin identity to VIEW state only. Never choose/save/restore. */
export function sourceTarget(project,hash=globalThis.location?.hash||''){
  const match=hash.match(/^#\/p\/([^?]+)\?(.*)$/);
  if(!match||match[1]!==project.id)return null;
  const q=new URLSearchParams(match[2]);
  const get=key=>q.get('origin_'+key)||null;
  const runId=get('run'),taskId=get('task'),outputId=get('output'),segmentId=get('segment'),final=get('final');
  if(![runId,taskId,outputId,segmentId,final].some(Boolean))return null;
  const base={asset:get('asset'),version:get('version'),media:get('media')};
  const unavailable=(message,category='generations')=>({...base,state:'unavailable',message,recycle:category});
  const found=position=>({...base,state:'found',message:'已定位来源记录；当前仅查看，项目选用与制作参数保持原样。',...position});
  const bad=()=>unavailable('来源记录不存在、已移除或标识不匹配；没有替换为最新结果。');
  if(project.kind==='image'||project.mode==='image_assets'){
    const out=outputId?project.outputs?.find(o=>o.id===outputId):null;
    const run=project.runs?.find(r=>r.id===(runId||out?.run));
    if((outputId&&!out)||(runId&&!run)||(out&&run&&out.run!==run.id))return bad();
    const task=project.tasks?.find(t=>t.id===(taskId||out?.task||run?.task));
    if(!task||task.discarded_at)return unavailable('来源编辑任务不存在或已废弃；可到项目类回收站检查。','projects');
    if((out&&out.task!==task.id)||(run&&run.task!==task.id)||out?.removed_at||run?.removed_at)return bad();
    // A run may produce multiple images. Do not guess which image was collected.
    const outputs=project.outputs?.filter(o=>o.run===run?.id&&!o.removed_at)||[];
    const selected=out||(outputs.length===1?outputs[0]:null);
    if((runId||outputId)&&!selected)return unavailable('来源运行没有唯一可定位的图片，请在原任务中核对候选。');
    return found({task:task.id,output:selected?.id,page:selected?'results':'edit'});
  }
  if(project.kind==='assembly'||project.mode==='video_assembly'){
    const run=project.assembly.runs.find(r=>r.id===runId);
    if(!run||run.removed_at)return bad();
    if(run.kind==='export')return found({step:2,run:run.id});
    if(run.kind!=='generate')return bad();
    const clip=project.assembly.clips.find(c=>c.extensions.some(e=>e.id===run.extension));
    const extension=clip?.extensions.find(e=>e.id===run.extension);
    if(!clip||clip.removed_at||extension.removed_at)return unavailable('所属视频或续写段已移除，请先在项目类回收站检查。','projects');
    return found({step:1,clip:clip.id,extension:extension.id,run:run.id});
  }
  if(final){
    if(final==='unknown')return unavailable('旧成片缺少确切导出标识，仅打开项目；当前成片可能已经变化。');
    const created=project.export?.created;
    const matches=created!=null&&(String(created)===final||(typeof created==='number'&&Number(final)===created));
    if(!matches)return unavailable('该次成片已不再是项目当前导出；资产库中的固定成片仍保留。');
    return found({tab:'export'});
  }
  const shot=project.segments.findIndex(s=>segmentId?s.id===segmentId:s.attempts?.some(a=>a.id===runId));
  if(shot<0)return bad();
  if(runId){
    const run=project.segments[shot].attempts?.find(a=>a.id===runId);
    if(!run||run.removed_at)return bad();
  }
  return found({tab:runId?'review':'edit',shot,run:runId});
}
