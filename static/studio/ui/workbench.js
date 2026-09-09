import {esc} from './primitives.js';
import {bindReadingPreviews} from './prompt-editor.js';

/** Slots are owned by the mode. Only layout and local view state are shared. */
export function workbench({rail='',canvas='',inspector='',kind=''}) {
  const controls=inspector&&!canvas.includes('data-toggle-inspector')?'<div class="workbench-view-tools"><button type="button" data-toggle-inspector class="quiet">收起属性</button></div>':'';
  return `<div class="director-desk ${esc(kind)}" data-has-rail="${!!rail}" data-has-inspector="${!!inspector}">${rail?`<aside class="desk-rail" aria-label="片段目录">${rail}</aside>`:''}<section class="desk-canvas">${controls}${canvas}</section>${inspector?`<aside class="desk-inspector" aria-label="本段属性">${inspector}</aside>`:''}</div>`;
}

export function propertyTabs(ctx,panels) {
  const chosen=panels.some(p=>p.id===ctx.inspectorTab)?ctx.inspectorTab:panels[0].id;
  return `<div class="property-tabs" role="tablist" aria-label="本段属性">${panels.map(p=>`<button type="button" role="tab" id="property-tab-${p.id}" aria-controls="property-${p.id}" aria-selected="${p.id===chosen}" tabindex="${p.id===chosen?0:-1}" data-property-tab="${p.id}">${esc(p.label)}</button>`).join('')}</div>${panels.map(p=>`<section class="property-panel" role="tabpanel" aria-labelledby="property-tab-${p.id}" id="property-${p.id}" ${p.id===chosen?'':'hidden'}>${p.html}</section>`).join('')}`;
}

export function bindWorkbench(ctx) {
  bindReadingPreviews(ctx.root);
  requestAnimationFrame(()=>fitWorkbench(ctx.root));
  const desk=ctx.root.querySelector('.director-desk');
  if(ctx.inspectorHidden===undefined)ctx.inspectorHidden=window.innerWidth>850&&window.innerWidth<1180;
  desk?.classList.toggle('inspector-collapsed',Boolean(ctx.inspectorHidden && ctx.root.querySelector('[data-toggle-inspector]')));
  ctx.root.querySelectorAll('[data-toggle-inspector]').forEach(button=>{
    button.textContent=ctx.inspectorHidden?'显示属性':'收起属性';
    button.setAttribute('aria-expanded',String(!ctx.inspectorHidden));
    button.onclick=()=>{ctx.inspectorHidden=!ctx.inspectorHidden;desk.classList.toggle('inspector-collapsed',ctx.inspectorHidden);button.textContent=ctx.inspectorHidden?'显示属性':'收起属性';button.setAttribute('aria-expanded',String(!ctx.inspectorHidden));};
  });
  const buttons=[...ctx.root.querySelectorAll('[data-property-tab]')];
  const select=(button,focus=false)=>{
    ctx.inspectorTab=button.dataset.propertyTab;
    buttons.forEach(b=>{const active=b===button;b.setAttribute('aria-selected',active);b.tabIndex=active?0:-1;
      ctx.root.querySelector('#property-'+b.dataset.propertyTab).hidden=!active;});
    if(focus)button.focus();
  };
  buttons.forEach((button,i)=>{
    button.onclick=()=>select(button);
    button.onkeydown=e=>{
      const keys={ArrowRight:(i+1)%buttons.length,ArrowLeft:(i+buttons.length-1)%buttons.length,Home:0,End:buttons.length-1};
      if(e.key in keys){e.preventDefault();select(buttons[keys[e.key]],true);}
    };
  });
}

export function fitWorkbench(root) {
  const desk=root.querySelector('.director-desk');if(!desk)return;
  const toolbar=root.querySelector('.savebar');
  const available=window.innerHeight-desk.getBoundingClientRect().top-(toolbar?.offsetHeight||60)-22;
  desk.style.setProperty('--desk-height',Math.max(260,available)+'px');
}
