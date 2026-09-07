"""Model choice -> temporary real API save -> offline graph, with no engine calls."""
import argparse
import html
import json
import re
import subprocess
import threading
import sys
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_video_assembly import AssemblyTests
from tests.video_assembly_ui_fixture import PAGE
from h3ui.video_assembly import compiler

CHECK = r'''
 await click('[data-step="1"]');await click('[data-add-extension]');await wait(settled);
 await click('#settings');
 const model=()=>document.querySelector('[data-param="model"]');
 const initial=model().value;
 const alternate=catalog.models.find(file=>file.endsWith('fixture-b.safetensors'));
 const choices=model().list?.options || model().options;
 const diagnostics={tag:model().tagName,count:choices?.length,current:initial,
   matchingCurrent:[...choices||[]].filter(o=>o.value.includes(initial)).length,
   directoryGap:document.querySelector('.settings-workbench').getBoundingClientRect().top-document.querySelector('[data-refresh]').getBoundingClientRect().bottom};
 document.body.dataset.diagnostics=JSON.stringify(diagnostics);
 assert(model().tagName==='SELECT','Current full filename filters native autocomplete; no unfiltered model select');
 for(const file of ['fixture-a.safetensors',alternate])assert([...model().options].some(o=>o.value===file),'catalog file missing: '+file);
 assert(diagnostics.directoryGap>=16,'refresh and category navigation touch');
 input('[data-param="model"]','fixture-a.safetensors');
 assert(model().value==='fixture-a.safetensors','redraw lost selection');
 await click('[data-cancel]');await click('#settings');assert(model().value===initial,'cancel changed model');
 input('[data-param="model"]',alternate);
 await click('[data-refresh]');await wait(()=>!document.querySelector('[data-refresh]').disabled);
 assert(model().value===alternate,'refresh changed model');
 input('[data-recipe]','official_image');input('[data-param="model"]','fixture-a.safetensors');
 input('[data-recipe]','dance_split');assert(model().value===alternate,'recipe lost model');
 const manual=model().closest('[data-model-field]').querySelector('details');manual.open=true;

 const custom=model().closest('[data-model-field]').querySelector('[data-model-filename]');
 custom.value='manual/not-scanned.safetensors';custom.dispatchEvent(new Event('input',{bubbles:true}));custom.dispatchEvent(new Event('change',{bubbles:true}));
 assert(model().value==='manual/not-scanned.safetensors','manual filename not selected');
 await click('[data-refresh]');await wait(()=>!document.querySelector('[data-refresh]').disabled);
 assert(model().value==='manual/not-scanned.safetensors','refresh discarded custom filename');
 await click('dialog [data-save]');await wait(()=>!document.querySelector('#dialog').open);
 const saved=await get(),extension=saved.assembly.clips[0].extensions[0];
 assert(extension.configurations.dance_split.model==='manual/not-scanned.safetensors','custom model not saved');
 assert(extension.configurations.official_image.model==='fixture-a.safetensors','directory choice not saved');
 await click('#settings');assert(model().value==='manual/not-scanned.safetensors','reopen lost custom');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True)
    AssemblyTests.setUpClass();case=AssemblyTests();case.setUp();checks=[]
    for name in ['fixture-a.safetensors','subdir/fixture-b.safetensors']:
        target=case.root/'comfy/models/diffusion_models'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'fixture filename only')
    page=PAGE.replace(" if(q.has('references')){", CHECK+"\n if(q.has('references')){")
    def application(environ,start_response):
        if environ.get('PATH_INFO')=='/model-check':
            start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
        return case.app(environ,start_response)
    class Quiet(WSGIRequestHandler):
        def log_message(self,*args):pass
    server=make_server('127.0.0.1',0,application,handler_class=Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        for width in [1280,760]:
            case.p=case.s.create('Model selection fixture');case.pid=case.p['id'];case.refresh();case.upload()
            result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+str(width))}',f'--window-size={width},1000','--virtual-time-budget=25000',f'--screenshot={out/(str(width)+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/model-check?pid={case.pid}'],capture_output=True,timeout=50)
            dom=result.stdout.decode('utf-8','replace');(out/f'{width}.html').write_text(dom,encoding='utf-8')
            match=re.search(r'data-check="([^"]+)"',dom);data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion')
            diag=re.search(r'data-diagnostics="([^"]+)"',dom);data['diagnostics']=json.loads(html.unescape(diag[1])) if diag else None
            if data['passed']:
                extension=case.refresh()['assembly']['clips'][0]['extensions'][0]
                for recipe,expected in [('dance_split','manual/not-scanned.safetensors'),('official_image','fixture-a.safetensors')]:
                    graph=compiler.compile_tail(case.st.recipes,case.pid,'fixture',extension['configurations'][recipe],compiler.plan(5)[0],0,'continue',dict(kind='external_decoded_av',frame_count=22,video='tail.mkv',audio='tail.wav'),'fixture')['workflow']
                    assert graph['1']['inputs']['unet_name']==expected
                data['offline_model_bindings']=True
            checks.append(dict(**data));print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();case.doCleanups();AssemblyTests.tearDownClass()
        (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
