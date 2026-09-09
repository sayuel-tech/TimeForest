import {mountPromptBrowser} from '../../features/prompt-library/browser.js';
export async function mountPromptLibrary(root,signal){
  root.classList.add('collection-page','prompt-library-page');
  root.innerHTML='<div class="library-header"><div><span class="eyebrow">PROMPT LIBRARY</span><h1>提示词库</h1><p>在创作中积累，按用途与模型整理，在下一次创作中复用。</p></div><a class="btn" href="/api/v5/prompt-library/backup" download>备份提示词库</a></div><div data-library></div>';
  await mountPromptBrowser(root.querySelector('[data-library]'),{signal});
}
