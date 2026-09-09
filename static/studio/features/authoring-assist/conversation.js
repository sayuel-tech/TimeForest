/** Scope is a content target, never a shared textarea across pages. */
export function writingScope(ctx, content) {
  if(ctx.step===1)return {layer:'screenplay',targets:[]};
  if(ctx.step===2)return {layer:ctx.assetTask==='asset_analysis'?'asset_bindings':'asset_screenplay',targets:[]};
  if(ctx.step===3)return {layer:ctx.splitShot?'segment':'storyboard',targets:ctx.selected?[ctx.selected]:[]};
  return {layer:ctx.clipTask==='rewrite'?'segment':'prompt',targets:ctx.selected?[ctx.selected]:[]};
}
export const conversationKey=({layer,targets})=>layer+':'+targets.join(',');
export function scopedJobs(project,scope){
  return project.creation_jobs.filter(j=>j.context?.target.layer===scope.layer&&JSON.stringify(j.context.target.target_ids)===JSON.stringify(scope.targets));
}
