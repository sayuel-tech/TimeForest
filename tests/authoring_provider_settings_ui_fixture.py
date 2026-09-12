"""Real temporary provider settings, cancel/apply/save/reopen; no model calls."""
from tests import authoring_manual_text_ui_fixture as fixture

fixture.SCRIPT=r'''<script type="module">
import {mountWorkspace} from '/static/studio/modes/authoring/workspace.js';
const root=document.querySelector('#root'),pid=new URLSearchParams(location.search).get('pid');
const get=()=>fetch('/api/v5/authoring/providers').then(r=>r.json()),pause=()=>new Promise(r=>setTimeout(r,40));
const assert=(v,m)=>{if(!v)throw Error(m)};
async function wait(fn){for(let i=0;i<350;i++){if(fn())return;await pause()}throw Error('Timed out')}
const $=s=>document.querySelector(s),set=(name,value)=>{const el=$('[data-config="'+name+'"]');el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}))};
try{
 const w=mountWorkspace(root,await fetch('/api/v5/projects/'+pid).then(r=>r.json()));
 const original=(await get()).items[0];
 async function open(){const old=$('[data-config="provider_kind"]');root.querySelector('#authoring-settings').click();await wait(()=>$('[data-config="provider_kind"]')&&$('[data-config="provider_kind"]')!==old);}
 await open();set('model_id','cancelled-model');$('[data-settings-action=cancel]').click();await pause();
 assert((await get()).items[0].model_id===original.model_id,'cancel wrote config');
 await open();set('provider_kind','openai_compatible');set('base_url','https://custom.invalid/v1');set('model_id','user-model');set('structured_mode','prompt_json');set('max_output_tokens','2048');
 $('[data-enabled]').click();$('[data-settings-action=apply]').click();await pause();
 assert((await get()).items[0].model_id===original.model_id,'apply wrote config');
 root.querySelector('[data-save]').click();await wait(()=>!w.session.working&&!w.session.actionPending);
 const saved=(await get()).items[0];assert(saved.provider_kind==='openai_compatible'&&saved.model_id==='user-model'&&saved.base_url==='https://custom.invalid/v1'&&saved.structured_mode==='prompt_json','save did not bind custom fields');
 await open();assert($('[data-config="model_id"]').value==='user-model','reopen lost model');
 set('model_id','second-model');$('[data-settings-action=save]').click();await wait(()=>!$('#dialog').open);
 assert((await get()).items[0].model_id==='second-model','direct save failed');await open();
 await document.fonts.ready;assert(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,modelCalls:0});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack})}
</script>'''

if __name__=='__main__':fixture.main()
