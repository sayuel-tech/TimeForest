// Only these recorded execution fields can change without replacing editor objects.
// State/identity/results stay in the content projection: they can change available actions.
const omit=(value,keys)=>Object.fromEntries(Object.entries(value||{}).filter(([key])=>!keys.includes(key)));
const runContent=run=>omit(run,['progress','note','phase','updated']);
export function projectContent(project){
  const value=omit(project,['revision','updated','updated_at','runtime','source_progress']);
  if(project.kind==='image')value.runs=(project.runs||[]).map(runContent);
  if(project.kind==='assembly')value.assembly={...project.assembly,runs:project.assembly.runs.map(runContent)};
  if(['authoring','movie'].includes(project.kind))value.creation_jobs=(project.creation_jobs||[]).map(runContent);
  return value;
}
export function mergeProjectRuntime(project,next){
  for(const key of ['busy','runtime','source_progress'])if(key in next)project[key]=next[key];
  if(project.kind==='image')project.runs=next.runs;
  if(project.kind==='assembly')project.assembly.runs=next.assembly.runs;
  if(['authoring','movie'].includes(project.kind))project.creation_jobs=next.creation_jobs;
}
export function acceptProjectRevision(project,next){
  for(const key of ['revision','updated','updated_at'])if(key in next)project[key]=next[key];
}
