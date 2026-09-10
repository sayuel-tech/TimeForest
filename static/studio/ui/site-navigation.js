/** No new routes, project writes, or automatic model calls. */
export function updateSiteNavigation(root,hash=location.hash||'#/'){
  const section=hash.startsWith('#/assets')?(new URLSearchParams(hash.split('?')[1]||'').get('view')==='trash'?'trash':new URLSearchParams(hash.split('?')[1]||'').get('view')==='storage'?'storage':'assets'):hash==='#/prompts'?'prompts':hash==='#/archive'||hash.startsWith('#/p/')?'projects':'home';
  document.querySelectorAll('[data-site-section]').forEach(link=>{
    const current=link.dataset.siteSection===section;
    link.classList.toggle('active',current);
    if(current)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
  });
  document.body.classList.toggle('tf-experience',!root.classList.contains('home-page'));
  document.body.classList.toggle('workspace-open',root.classList.contains('project-page'));
}
export function mountSiteNavigation(root){
  document.querySelector('[data-skip-workspace]')?.addEventListener('click',event=>{event.preventDefault();root.focus();});
  updateSiteNavigation(root);
  const observer=new MutationObserver(()=>updateSiteNavigation(root));
  // Only a route's root class, never editor content, media elements, or task progress.
  observer.observe(root,{attributes:true,attributeFilter:['class']});
  const header=document.querySelector('.site-header');
  const measure=()=>{if(header){document.documentElement.style.setProperty('--site-header-height',header.getBoundingClientRect().height+'px');root.querySelectorAll('.director-desk').forEach(desk=>desk.dispatchEvent(new Event('workbench:resize')));}};
  const resize=header?new ResizeObserver(measure):null;if(header)resize.observe(header);measure();
  const refresh=()=>queueMicrotask(()=>updateSiteNavigation(root));window.addEventListener('hashchange',refresh);
  return ()=>{observer.disconnect();resize?.disconnect();window.removeEventListener('hashchange',refresh);};
}
