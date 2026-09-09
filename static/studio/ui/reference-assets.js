import {assetVersionLink} from './asset-origin.js';
import {esc,fmt} from './primitives.js';

export function importOptions(items) {
  return `<div class="asset-commands import-options">${items.join('')}</div>`;
}
export function referenceAssetCard(asset,{inherited=false,actions=''}={}) {
  const purpose={character:'角色',face:'脸部',costume:'服装',scene:'场景',palette:'色系',prop:'道具',voice:'音色参考'};
  return `<div data-view-key="reference:${esc(JSON.stringify([asset.id||asset.library_reference?.asset||asset.url,asset.library_reference?.version,asset.purpose,asset.subject]))}" class="asset ${inherited?'inherited':''}">${asset.kind==='image'?`<img src="${esc(asset.url)}" alt="${esc(asset.name)}">`:asset.kind==='audio'?`<audio controls preload="none" src="${esc(asset.url)}"></audio>`:''}<h4>${esc(asset.name)}</h4><small>${esc(purpose[asset.purpose]||asset.purpose)} ${asset.subject?'· 角色'+esc(asset.subject):''}</small>${asset.duration?`<small>${fmt(asset.duration)}秒</small>`:''}${assetVersionLink(asset.library_reference)}${actions?`<details class="asset-menu"><summary>管理素材</summary>${actions}</details>`:''}</div>`;
}
