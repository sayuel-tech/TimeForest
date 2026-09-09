// Internal source links carry selection/view state, never executable URLs.
const id=value=>typeof value==='string'&&/^(?:[a-f0-9]{32}|[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12})$/.test(value);
export function readReturnContext(search){
  try{const value=JSON.parse(search.get('return_context')||'null');
    if(!value||!id(value.origin_movie_id)||!['generation','editing'].includes(value.origin_page))return null;
    for(const key of ['origin_item_id','origin_segment_id','viewed_take_id','script_project_id','script_target_id','source_bundle_id'])if(value[key]!==null&&!id(value[key]))return null;
    if(!value.view||!Number.isFinite(value.view.zoom)||value.view.zoom<=0)return null;
    return value;
  }catch{return null;}
}
export function returnHref(value){
  const query=new URLSearchParams({step:value.origin_page==='editing'?'1':'0',target:value.origin_segment_id||'',item:value.origin_item_id||'',take:value.viewed_take_id||'',zoom:String(value.view.zoom),scroll_x:String(Math.max(0,Number(value.view.scroll_x)||0))});
  return '#/p/'+value.origin_movie_id+'?'+query;
}
export function withReturnContext(href,value){const [path,search='']=href.split('?'),query=new URLSearchParams(search);query.set('return_context',JSON.stringify(value));return path+'?'+query;}
