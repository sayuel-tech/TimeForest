import {esc, status} from './primitives.js';
import {productionSettingsAction} from './production-settings.js';

/** Shared product header. Rendering never changes the project's saved state. */
export function workspaceHeader({name, code, modeName, state, stateLabel, summary='', titleId, statusId, settings=null}) {
  const badge=stateLabel ? `<span class="badge" ${statusId?`id="${esc(statusId)}"`:''}>${esc(stateLabel)}</span>` : state ? status(state) : '';
  return `<div class="project-head" data-workspace-header data-workspace-mode="${esc(code)}"><div class="workspace-identity"><a class="back-link" href="#/archive" aria-label="返回项目档案">项目档案 <span aria-hidden="true">／</span></a><div class="workspace-title-line"><h1 ${titleId?`id="${esc(titleId)}"`:''} title="${esc(name)}">${esc(name)}</h1>${badge}</div><div class="project-kicker"><span class="eyebrow">${esc(modeName)}</span><span class="project-summary">${esc(summary)}</span></div></div>${settings?productionSettingsAction(settings):''}</div>`;
}

/** Stages describe location, not completion. No checkmark is inferred from order. */
export function workspaceSteps({items, current, label, attribute='data-tab'}) {
  if (!['data-tab','data-page','data-step'].includes(attribute)) throw new Error('未知步骤适配属性');
  return `<nav class="steps" data-workspace-steps aria-label="${esc(label)}">${items.map(([key,title,reason],i)=>`<button type="button" ${attribute}="${esc(key)}" data-workspace-step="${esc(key)}" class="${String(current)===String(key)?'active':''}" aria-current="${String(current)===String(key)?'step':'false'}" ${reason?`disabled title="${esc(reason)}"`:''}><span class="workspace-step-number" aria-hidden="true">${i+1}</span><span class="workspace-step-label">${esc(title)}</span></button>`).join('')}</nav>`;
}

export function bindWorkspaceSteps(root) {
  const nav=root.querySelector('[data-workspace-steps]');
  if (!nav) return;
  nav.onkeydown=event=>{
    const buttons=[...nav.querySelectorAll('[data-workspace-step]')].filter(button=>!button.disabled);
    const index=buttons.indexOf(event.target);
    if(index<0 || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();
    const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
    buttons[next]?.focus();
  };
  // A fresh stage may have been reached through the object directory.
  const active=nav.querySelector('[aria-current="step"]');
  if(active){const left=active.offsetLeft-nav.offsetLeft;if(left<nav.scrollLeft||left+active.offsetWidth>nav.scrollLeft+nav.clientWidth)nav.scrollLeft=Math.max(0,left-20);}
}
