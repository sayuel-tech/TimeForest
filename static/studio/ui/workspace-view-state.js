// View state belongs to a project/page/selection, never to its persisted draft.
// Capture both open and closed: restoring only open items reopens default-open ones.
export function workspaceViewState(root) {
  const states=new Map();let renderedScope=null;
  const scrollSelectors=['.desk-rail','.desk-canvas','.desk-inspector','.property-panel','.movie-timeline','.review-media','.prompt-text','.prompt-entry-list','[data-view-scroll]'];
  function disclosures(){
    const counts=new Map(),keys=new Map();
    for(const el of root.querySelectorAll('details')){
      const parent=el.parentElement.closest('details'),owner=el.closest('[data-view-key]');
      const label=owner===el?'':el.querySelector(':scope > summary')?.textContent.trim()||'';
      const base=JSON.stringify([keys.get(parent)||'',owner?.dataset.viewKey||'',label]);
      const count=counts.get(base)||0;counts.set(base,count+1);keys.set(el,base+':'+count);
    }
    return keys;
  }
  return {
    beforeRender(scope){
      if(renderedScope!==null){
        const details=disclosures(),active=root.ownerDocument.activeElement;
        states.set(renderedScope,{
          details:new Map([...details].map(([el,key])=>[key,el.open])),
          focusedControl:root.contains(active)&&active?.matches('input,textarea,select,button,a')?{id:active.id,tag:active.tagName,name:active.getAttribute('name'),data:{...active.dataset},start:active.selectionStart,end:active.selectionEnd}:null,
          focusedSummary:active?.tagName==='SUMMARY'?details.get(active.parentElement):null,
          scrolls:scrollSelectors.flatMap(selector=>[...root.querySelectorAll(selector)].map((el,index)=>({selector,index,id:el.id,top:el.scrollTop,left:el.scrollLeft}))),
          media:renderedScope===scope?[...root.querySelectorAll('video[src],audio[src]')]:[],
          page:[root.ownerDocument.defaultView.scrollX,root.ownerDocument.defaultView.scrollY],
        });
      }
      const sameScope=renderedScope===scope;renderedScope=scope;
      const previous=states.get(scope);
      return ()=>{
        if(!previous)return;
        for(const [el,key] of disclosures()){
          if(previous.details.has(key))el.open=previous.details.get(key);
          if(key===previous.focusedSummary)el.querySelector(':scope > summary')?.focus({preventScroll:true});
        }
        // Preserve playback elements only in a render of the same viewed object.
        if(sameScope){const old=[...previous.media];for(const el of root.querySelectorAll('video[src],audio[src]')){
          const index=old.findIndex(m=>m.tagName===el.tagName&&m.getAttribute('src')===el.getAttribute('src'));
          if(index>=0)el.replaceWith(old.splice(index,1)[0]);
        }}
        const focus=previous.focusedControl;
        if(sameScope&&focus){const target=[...root.querySelectorAll(focus.tag)].find(el=>focus.id?el.id===focus.id:(focus.name?el.getAttribute('name')===focus.name:Object.keys(focus.data).length&&Object.entries(focus.data).every(([k,v])=>el.dataset[k]===v)));target?.focus({preventScroll:true});if(target?.setSelectionRange&&focus.start!=null)try{target.setSelectionRange(focus.start,focus.end);}catch{}}
        for(const s of previous.scrolls){const elements=[...root.querySelectorAll(s.selector)];const el=s.id?elements.find(el=>el.id===s.id):elements[s.index];if(el){el.scrollTop=s.top;el.scrollLeft=s.left;}}
        root.ownerDocument.defaultView.scrollTo({left:previous.page[0],top:previous.page[1],behavior:'instant'});
        previous.media=[];
      };
    },
    dispose(){states.clear();renderedScope=null;},
  };
}
