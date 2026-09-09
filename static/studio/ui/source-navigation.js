import {esc} from './primitives.js';
import {assetVersionLink} from './asset-origin.js';

export function showSourceNavigation(root,target){
  root.querySelector('[data-source-navigation]')?.remove();
  if(!target||target.dismissed)return;
  const html=`<aside class="notice row between" data-source-navigation role="status"><span>${esc(target.message)}</span><div class="row">${target.returnHref?.startsWith('#/p/')?`<a href="${esc(target.returnHref)}">${esc(target.returnLabel||'返回原片段')}</a>`:assetVersionLink(target,'返回来源资产')}${target.recycle?`<a href="#/assets?view=trash&amp;recycle=${esc(target.recycle)}">查看对应回收站</a>`:''}<button type="button" class="quiet" data-dismiss-source>关闭提示</button></div></aside>`;
  const anchor=root.querySelector('.steps');
  if(anchor)anchor.insertAdjacentHTML('afterend',html);else root.insertAdjacentHTML('afterbegin',html);
  root.querySelector('[data-dismiss-source]').onclick=()=>{target.dismissed=true;root.querySelector('[data-source-navigation]')?.remove();};
}
