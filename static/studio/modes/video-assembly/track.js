/** Delivery slots; reordering never changes an extension's generation parent. */
export function trackItems(p){
  const rows=[];
  for(const c of p.assembly.clips.filter(c=>!c.removed_at)){
    rows.push({key:'clip:'+c.id,clip:c,id:c.id,name:c.name,url:c.url,cover:c.cover_url,seconds:c.end-c.start});
    c.extensions.forEach((e,i)=>{
      const run=p.assembly.runs.find(r=>r.id===e.selected&&r.extension===e.id&&r.state==='success'&&!r.removed_at);
      if(!e.removed_at&&run)rows.push({key:'extension:'+e.id,clip:c,extension:e,run,id:e.id,name:`${c.name} · 续接 ${i+1}`,url:run.url,cover:run.cover_url,seconds:run.report.duration});
    });
  }
  const byKey=new Map(rows.map(row=>[row.key,row]));
  return [...new Set([...(p.assembly.track_order||[]),...byKey.keys()])].filter(key=>byKey.has(key)).map(key=>byKey.get(key));
}

export function moveTrack(p,key,offset){
  const order=trackItems(p).map(row=>row.key),index=order.indexOf(key),to=index+offset;
  if(index<0||to<0||to>=order.length)return p;
  order.splice(to,0,...order.splice(index,1));
  return {...p,assembly:{...p.assembly,track_order:order}};
}
