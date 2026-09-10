import {esc} from './primitives.js';
import {bindReadingPreviews} from './prompt-editor.js';

/** The modes own their data and slots. This component owns spatial navigation only. */
export function workbench({rail='',canvas='',inspector='',kind='',railLabel='创作目录',inspectorLabel='当前参考与来源'}) {
  const controls=(rail||inspector)?`<div class="workbench-view-tools">${rail?'<button type="button" data-toggle-directory class="quiet" aria-expanded="false">目录</button>':''}${inspector&&!canvas.includes('data-toggle-inspector')?'<button type="button" data-toggle-inspector class="quiet">收起侧栏</button>':''}</div>`:'';
  return `<div class="director-desk ${esc(kind)}" data-has-rail="${!!rail}" data-has-inspector="${!!inspector}">${rail?`<aside class="desk-rail" aria-label="${esc(railLabel)}"><button type="button" class="desk-drawer-close" data-close-directory>关闭目录 ×</button>${rail}</aside>`:''}<section class="desk-canvas" aria-label="当前创作内容">${controls}${canvas}</section>${inspector?`<aside class="desk-inspector" aria-label="${esc(inspectorLabel)}"><button type="button" class="desk-drawer-close" data-close-inspector>关闭侧栏 ×</button>${inspector}</aside>`:''}<button type="button" class="desk-backdrop" data-close-drawers tabindex="-1" aria-label="返回工作区" hidden></button></div>`;
}

export function propertyTabs(ctx,panels) {
  if(!panels.length)return '';
  const chosen=panels.some(p=>p.id===ctx.inspectorTab)?ctx.inspectorTab:panels[0].id;
  return `<div class="property-tabs" role="tablist" aria-label="当前参考与来源">${panels.map(p=>`<button type="button" role="tab" id="property-tab-${esc(p.id)}" aria-controls="property-${esc(p.id)}" aria-selected="${p.id===chosen}" tabindex="${p.id===chosen?0:-1}" data-property-tab="${esc(p.id)}">${esc(p.label)}</button>`).join('')}</div>${panels.map(p=>`<section class="property-panel" role="tabpanel" aria-labelledby="property-tab-${esc(p.id)}" id="property-${esc(p.id)}" ${p.id===chosen?'':'hidden'}>${p.html}</section>`).join('')}`;
}

export function bindWorkbench(ctx) {
  bindReadingPreviews(ctx.root);
  requestAnimationFrame(()=>fitWorkbench(ctx.root));
  const desk=ctx.root.querySelector('.director-desk');
  if(!desk)return;
  const canvas=desk.querySelector('.desk-canvas');
  const narrowNow=window.innerWidth<1180;
  if(ctx.inspectorHidden===undefined||(narrowNow&&ctx._workbenchNarrow!==true))ctx.inspectorHidden=narrowNow;
  ctx._workbenchNarrow=narrowNow;
  let directoryOpen=!!ctx.directoryOpen;
  let focusOrigin=null;
  const inspectorButtons=[...ctx.root.querySelectorAll('[data-toggle-inspector]')];
  const directoryButtons=[...desk.querySelectorAll('[data-toggle-directory]')];
  const closeDrawers=(returnFocus=true)=>{
    directoryOpen=false;
    if(window.innerWidth<1180)ctx.inspectorHidden=true;
    apply();
    if(returnFocus&&focusOrigin?.isConnected)focusOrigin.focus({preventScroll:true});
  };
  function apply(){
    const narrow=window.innerWidth<1180;
    const railDrawer=directoryOpen&&window.innerWidth<850;
    const inspectorDrawer=narrow&&!ctx.inspectorHidden&&!!desk.querySelector('.desk-inspector');
    desk.classList.toggle('inspector-collapsed',Boolean(ctx.inspectorHidden&&inspectorButtons.length));
    ctx.directoryOpen=directoryOpen;
    desk.classList.toggle('directory-open',railDrawer);
    desk.classList.toggle('inspector-open',inspectorDrawer);
    desk.querySelector('.desk-backdrop').hidden=!(railDrawer||inspectorDrawer);
    inspectorButtons.forEach(b=>{b.textContent=ctx.inspectorHidden?'展开侧栏':'收起侧栏';b.setAttribute('aria-expanded',String(!ctx.inspectorHidden));});
    directoryButtons.forEach(b=>b.setAttribute('aria-expanded',String(railDrawer)));
    // Responsive drawers are complementary, not fake modal dialogs.
    canvas.classList.toggle('drawer-behind',railDrawer||inspectorDrawer);
    canvas.inert=railDrawer||inspectorDrawer;
    const rail=desk.querySelector('.desk-rail'),inspector=desk.querySelector('.desk-inspector');
    if(rail)rail.inert=inspectorDrawer;
    if(inspector)inspector.inert=railDrawer;
  }
  inspectorButtons.forEach(button=>{button.onclick=()=>{
    focusOrigin=button;directoryOpen=false;ctx.inspectorHidden=!ctx.inspectorHidden;apply();
    if(window.innerWidth<1180&&!ctx.inspectorHidden)desk.querySelector('[data-close-inspector]')?.focus();
  };});
  directoryButtons.forEach(button=>{button.onclick=()=>{
    focusOrigin=button;directoryOpen=!directoryOpen;ctx.inspectorHidden=true;apply();
    if(directoryOpen)desk.querySelector('[data-close-directory]')?.focus();
  };});
  desk.querySelectorAll('[data-close-directory],[data-close-inspector],[data-close-drawers]').forEach(button=>button.onclick=()=>closeDrawers());
  desk.onkeydown=event=>{if(event.key==='Escape'&&(directoryOpen||desk.classList.contains('inspector-open'))){event.preventDefault();closeDrawers();}};
  const buttons=[...ctx.root.querySelectorAll('[data-property-tab]')];
  const select=(button,focus=false)=>{
    ctx.inspectorTab=button.dataset.propertyTab;
    buttons.forEach(b=>{
      const active=b===button;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;
      const panel=ctx.root.querySelector('#'+CSS.escape('property-'+b.dataset.propertyTab));if(panel)panel.hidden=!active;
    });
    if(focus)button.focus();
  };
  buttons.forEach((button,i)=>{
    button.onclick=()=>select(button);
    button.onkeydown=event=>{
      const keys={ArrowRight:(i+1)%buttons.length,ArrowLeft:(i+buttons.length-1)%buttons.length,Home:0,End:buttons.length-1};
      if(event.key in keys){event.preventDefault();select(buttons[keys[event.key]],true);}
    };
  });
  desk.addEventListener('workbench:resize',()=>{fitWorkbench(ctx.root);const next=window.innerWidth<1180;if(next&&!ctx._workbenchNarrow)ctx.inspectorHidden=true;ctx._workbenchNarrow=next;directoryOpen=false;apply();});
  desk.addEventListener('click',event=>{if(event.target.closest('[data-select],[data-nav-step],[data-task],[data-shot],[data-clip],[data-extension]'))closeDrawers(false);});
  apply();
}

export function fitWorkbench(root) {
  const desk=root.querySelector('.director-desk');if(!desk)return;
  const toolbar=root.querySelector('.savebar');
  const available=window.innerHeight-desk.getBoundingClientRect().top-(toolbar?.offsetHeight||60);
  desk.style.setProperty('--desk-height',Math.max(240,available)+'px');
}

// One application-lifetime listener; no polling, observer per render, or retained roots.
let resizeFrame=0;
if(typeof window!=='undefined')window.addEventListener('resize',()=>{
  cancelAnimationFrame(resizeFrame);
  resizeFrame=requestAnimationFrame(()=>document.querySelectorAll('.director-desk').forEach(desk=>{
    const root=desk.closest('.project-page')||desk.parentElement;fitWorkbench(root);
    desk.dispatchEvent(new Event('workbench:resize'));
  }));
});
