/** Input destinations describe business locations, not a shared project shape. */
const destinations={swap:'segment',image_story:'segment',text_story:'segment',video_assembly:'extension'};
export const acceptsImage = project => !!destinations[project.mode]&&!project.deleted_at;
export function imageDestinations(project){
  if(destinations[project.mode]==='extension')return (project.assembly?.clips||[])
    .filter(c=>!c.removed_at).flatMap(c=>c.extensions.filter(e=>!e.removed_at)
      .map((e,i)=>({id:e.id,label:`${c.name} · 续写 ${i+1}`,kind:'extension'})));
  if(destinations[project.mode]==='segment')return (project.segments||[])
    .map((s,i)=>({id:s.id,label:`P${String(i+1).padStart(2,'0')}`,kind:'segment'}));
  return [];
}
