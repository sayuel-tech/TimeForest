// Small status-only regions. Never use this to reconcile editors or rebind closures.
// Retains keyed task rows, disclosure state, focus and unchanged nodes as progress arrives.
const keys=['data-view-key','data-status-key','id'];
const keyOf=node=>node.nodeType===1?keys.map(key=>node.getAttribute(key)||'').join('|'):'';
function patch(old,next){
  if(old.nodeType===3||old.nodeType===8){if(old.data!==next.data)old.data=next.data;return;}
  if(old.nodeType!==1)return;
  for(const attr of [...old.attributes])if(!(old.tagName==='DETAILS'&&attr.name==='open')&&!next.hasAttribute(attr.name))old.removeAttribute(attr.name);
  for(const attr of next.attributes)if(!(old.tagName==='DETAILS'&&attr.name==='open')&&old.getAttribute(attr.name)!==attr.value)old.setAttribute(attr.name,attr.value);
  reconcile(old,next);
}
function reconcile(root,fresh){
  const available=[...root.childNodes];let cursor=root.firstChild;
  for(const next of [...fresh.childNodes]){
    const key=keyOf(next),compatible=old=>old.nodeType===next.nodeType&&old.nodeName===next.nodeName&&keyOf(old)===key;
    let old=available.find(node=>compatible(node));
    if(old){available.splice(available.indexOf(old),1);if(old!==cursor)root.insertBefore(old,cursor);patch(old,next);}
    else {old=next.cloneNode(true);root.insertBefore(old,cursor);}
    cursor=old.nextSibling;
  }
  available.forEach(node=>node.remove());
}
export function updateStatusRegion(root,markup){
  if(!root)return;
  const focused=root.ownerDocument.activeElement;
  const retainedFocus=root.contains(focused)?focused:null;
  const template=root.ownerDocument.createElement('template');template.innerHTML=markup;
  reconcile(root,template.content);
  if(retainedFocus&&root.contains(retainedFocus)&&root.ownerDocument.activeElement!==retainedFocus)retainedFocus.focus({preventScroll:true});
}
