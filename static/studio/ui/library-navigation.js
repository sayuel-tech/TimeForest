import {esc} from './primitives.js';
// Asset and prompt libraries share hierarchy, selected state and keyboard-native controls.
export function libraryNavigation({label,groups}){
  const item=value=>{
    const children=value.children||[],tag=value.href?'a':'button';
    const attrs=value.href?`href="${esc(value.href)}"`:'type="button"';
    const data=Object.entries(value.data||{}).map(([key,v])=>`data-${key}="${esc(v)}"`).join(' ');
    return `<div class="collection-nav-item"><${tag} ${attrs} ${data} class="collection-nav-link ${value.active?'active':''} ${value.expanded?'is-ancestor':''}" ${value.active?'aria-current="page"':''} ${value.expandable?`aria-expanded="${!!value.expanded}"`:''}><span>${esc(value.label)}</span>${value.expandable?`<span aria-hidden="true">${value.expanded?'▾':'›'}</span>`:''}</${tag}>${children.length?`<div class="collection-nav-children">${children.map(item).join('')}</div>`:''}</div>`;
  };
  return `<nav class="collection-navigation" aria-label="${esc(label)}">${groups.map(group=>`<section class="collection-nav-group">${group.label?`<h2>${esc(group.label)}</h2>`:''}${group.items.map(item).join('')}</section>`).join('')}</nav>`;
}
