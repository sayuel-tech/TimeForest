import {scopedModal} from '../../ui/primitives.js';
import {importOptions} from '../../ui/reference-assets.js';
export function openLibraryImports({signal,folder,pack}){
  const dialog=scopedModal(`<div class="dialog-heading"><span class="eyebrow">IMPORT MATERIALS</span><h2>更多导入方式</h2><p class="helper">按素材所在的位置选择；普通图片、视频和声音可直接使用页头的“导入素材”。</p></div>${importOptions([
    '<section class="import-option"><button data-folder>收集输出文件夹</button><p class="helper">先检查本机文件夹内容，再选择需要收集的素材。</p></section>',
    '<section class="import-option"><button data-pack>导入素材包</button><input data-pack-file type="file" accept=".zip" hidden><p class="helper">选择导出的 ZIP 素材包，核对内容后导入。</p></section>',
  ])}<div class="dialog-actions"><button data-close>取消</button></div>`);
  const close=()=>dialog.close();signal?.addEventListener('abort',close,{once:true});
  dialog.addEventListener('close',()=>signal?.removeEventListener('abort',close),{once:true});
  dialog.querySelector('[data-close]').onclick=close;
  dialog.querySelector('[data-folder]').onclick=()=>{close();folder();};
  dialog.querySelector('[data-pack]').onclick=()=>dialog.querySelector('[data-pack-file]').click();
  dialog.querySelector('[data-pack-file]').onchange=e=>{const file=e.target.files[0];if(file){close();pack(file);}};
}
