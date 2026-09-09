import {esc} from './primitives.js';

// The existing .empty framework owns typography, spacing and responsive sizing.
export function illustratedEmpty({image,title='',text='',actions=''}) {
  return `<div class="empty"><img data-decorative-art src="${esc(image)}" alt="" width="240" height="160">${title?`<h3>${esc(title)}</h3>`:''}${text?`<p>${esc(text)}</p>`:''}${actions}</div>`;
}

// Artwork is decorative: a failed asset must not hide the meaning or actions.
export function bindDecorativeArt(root) {
  root.querySelectorAll('[data-decorative-art]').forEach(img=>{
    img.onerror=()=>{img.hidden=true;};
    if(img.complete&&!img.naturalWidth)img.hidden=true;
  });
}
