"""Real temporary image API and browser uploads, with all engine calls forbidden."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests import uiux_image_canvas_fixture as fixture

fixture.SCRIPT = r'''<script type="module">
const pause=()=>new Promise(r=>setTimeout(r,70)),assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async f=>{for(let i=0;i<250;i++){if(await f())return;await pause()}throw Error('Timed out '+f)};
const root=document.querySelector('#app'),pid=location.hash.split('/')[2];
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
async function click(s){const el=root.querySelector(s)||document.querySelector(s);assert(el,'Missing '+s);el.click();await pause()}
try{
 await wait(()=>root.querySelector('[data-tool]'));
 const initial=await get(),dual=initial.tasks.find(t=>t.submode==='dual');
 await click('[data-toggle-directory]');await click('[data-task="'+dual.id+'"]');
 await wait(()=>root.querySelector('[data-tool=dual][aria-pressed=true]'));
 if(root.querySelector('.director-desk').classList.contains('directory-open'))await click('[data-close-directory]');
 const assets=root.querySelector('#property-assets');
 assert(assets.querySelectorAll('[data-upload]').length===2,'Default must have two slots');
 // Every upload goes through the real /inputs route with a synthetic image.
 const source=initial.inputs.find(i=>i.id===dual.A),blob=await fetch(source.url).then(r=>r.blob());
 for(const role of 'CDEFGHI'){
   await click('#image-add-reference');
   const field=root.querySelector('[data-upload="'+role+'"]');assert(field,'Missing slot '+role);
   const transfer=new DataTransfer();transfer.items.add(new File([blob],role+'.png',{type:'image/png'}));
   field.files=transfer.files;field.dispatchEvent(new Event('change',{bubbles:true}));
   await wait(()=>root.querySelector('[data-upload="'+role+'"]')!==field);
 }
 assert(root.querySelector('#image-add-reference').disabled,'Tenth slot enabled');
 assert(root.querySelector('#property-assets').querySelectorAll('[data-upload]').length===9,'Nine slots not rendered');
 await click('#image-save');await wait(async()=>Boolean((await get()).tasks.find(t=>t.id===dual.id).I));
 const saved=await get(),oldTask=saved.tasks.find(t=>t.id===dual.id);
 assert('ABCDEFGHI'.split('').every(role=>oldTask[role]),'References lost during real save');
 // Cancel removal must not save or change the live draft.
 await click('[data-drop-image-slot=C]');
 const dialog=document.querySelector('dialog[open]');assert(dialog,'Missing removal confirmation');
 const cancel=[...dialog.querySelectorAll('button')].find(b=>b.textContent.includes('取消'));assert(cancel,'Missing cancel');cancel.click();await pause();
 assert(root.querySelector('[data-upload=C]'),'Cancel removed reference');
 assert((await get()).revision===saved.revision,'Cancel saved project');
 await click('[data-drop-image-slot=C]');
 const confirm=[...document.querySelector('dialog[open]').querySelectorAll('button')].find(b=>b.textContent.trim()==='移除引用');confirm.click();
 await wait(()=>!root.querySelector('[data-upload=C]'));
 assert(root.querySelector('[data-upload=D]'),'Removing C relabeled D');
 await click('#image-save');await wait(async()=>!Object.hasOwn((await get()).tasks.find(t=>t.id===dual.id),'C'));
 await click('#image-add-reference');await wait(()=>root.querySelector('[data-upload=C]'));
 await click('#image-save');await wait(async()=>Object.hasOwn((await get()).tasks.find(t=>t.id===dual.id),'C'));
 // Leave and reopen via the real application router, retaining optional empties.
 location.hash='#/';await wait(()=>!root.querySelector('[data-tool]'));location.hash='#/p/'+pid;
 await wait(()=>root.querySelector('[data-upload=I]'));
 assert(root.querySelectorAll('#property-assets [data-upload]').length===9,'Reopen lost empty C or extra inputs');
 const reopened=(await get()).tasks.find(t=>t.id===dual.id);
 assert(reopened.C===null&&reopened.D===oldTask.D&&reopened.I===oldTask.I,'Sparse input identities lost');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'Horizontal page overflow');
 if(innerWidth<700&&!root.querySelector('.director-desk').classList.contains('inspector-open'))await click('[data-toggle-inspector]');
 root.querySelector('#image-add-reference').scrollIntoView({block:'nearest'});
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,checks:['default two','seven real uploads','nine limit','real save','cancel keeps revision','remove C preserves D','empty slots persist','reopen','no overflow']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack})}
</script>'''

if __name__ == '__main__': fixture.main()
