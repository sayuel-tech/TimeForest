import {esc} from './primitives.js';

/** Display state is separate from selection and collection; adapters own all commands. */
export function candidateState({viewing=false,selected=false,collected=false}={}) {
  return `<span class="candidate-state">${viewing?'<span>正在查看</span>':''}${selected?'<span class="badge">已选用</span>':''}${collected?'<span class="badge">已入库</span>':''}</span>`;
}

export function candidateButton({id,number,label='候选',state='',selected=false,viewing=false,collected=false,preview='',detail='',attribute}) {
  if(!['data-output','data-run-view'].includes(attribute))throw Error('未知候选查看适配');
  return `<button type="button" ${attribute}="${esc(id)}" aria-pressed="${viewing}" class="candidate-choice">${preview}<span>${esc(label)} ${esc(number)}${state?' · '+esc(state):''}</span>${candidateState({viewing,selected,collected})}${detail?`<small>${esc(detail)}</small>`:''}</button>`;
}

export function resultActions({inspect='',decide='',collect='',note=''}={}) {
  return `<div class="review-actions result-actions">${note?`<div class="result-note">${note}</div>`:''}<div class="result-interactions">${inspect?`<div class="row result-inspect">${inspect}</div>`:''}${decide?`<div class="row result-decide">${decide}</div>`:''}</div>${collect?`<div class="row result-collect">${collect}</div>`:''}</div>`;
}

export function collectionActions({url,media='视频',asset,button='',filename=''}) {
  return `${url?`<a class="btn quiet" href="${esc(url)}" download="${esc(filename)}">下载${esc(media)}</a>`:''}${asset?`<a class="btn quiet" href="#/assets/${esc(asset)}">已入库 · 查看资产</a>`:button}`;
}
