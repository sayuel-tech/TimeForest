import {esc, status} from './primitives.js';
import {productionSettingsAction} from './production-settings.js';

/** One header template; modes supply text, status and the existing action ID. */
export function workspaceHeader({name, code, modeName, state, stateLabel, summary='', titleId, statusId, settings=null}) {
  const badge=stateLabel ? `<span class="badge" ${statusId?`id="${esc(statusId)}"`:''}>${esc(stateLabel)}</span>` : state ? status(state) : '';
  return `<div class="project-head" data-workspace-header><div><a class="back-link" href="#/archive">← 项目档案</a><div class="project-kicker"><span class="eyebrow">${esc(code)} · ${esc(modeName)}</span>${badge}</div><h1 ${titleId?`id="${esc(titleId)}"`:''} title="${esc(name)}">${esc(name)}</h1><div class="muted project-summary">${esc(summary)}</div></div>${settings?productionSettingsAction(settings):''}</div>`;
}

/** Retain adapter selectors and step IDs; navigation never submits a business action. */
export function workspaceSteps({items, current, label, attribute='data-tab'}) {
  if (!['data-tab','data-page','data-step'].includes(attribute)) throw new Error('未知步骤适配属性');
  return `<nav class="steps" data-workspace-steps aria-label="${esc(label)}">${items.map(([key,title,reason],i)=>`<button type="button" ${attribute}="${esc(key)}" data-workspace-step="${esc(key)}" class="${String(current)===String(key)?'active':''}" aria-current="${String(current)===String(key)?'step':'false'}" ${reason?`disabled title="${esc(reason)}"`:''}><span aria-hidden="true">${String(i+1).padStart(2,'0')}</span>${esc(title)}</button>`).join('')}</nav>`;
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
    // Enter/Space use native button clicks, preserving each mode's save/prepare gate.
  };
}
