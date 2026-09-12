"""Real swap UI, controlled API/media fixtures; no production or generation."""
import argparse
import json
import html
import re
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.result_experience_ui_fixture import ResultFixture, Handler
from tests.uiux_browser_capture import capture
from tests.test_video_assembly_track import TrackTests

SCRIPT='''<script type="module">
const wait=async f=>{for(let i=0;i<200;i++){if(f())return;await new Promise(r=>setTimeout(r,50));}throw Error('UI timeout');};
const assert=(v,m)=>{if(!v)throw Error(m)};
try{
 const step=new URLSearchParams(location.search).get('step');
 await wait(()=>document.querySelector('[data-workspace-step="'+step+'"]'));
 document.querySelector('[data-workspace-step="'+step+'"]').click();
 await wait(()=>document.querySelector(step==='source'?'.source-desk':'.swap-comparison'));
 await document.fonts.ready;
 await wait(()=>[...document.querySelectorAll('.source-desk video,.swap-comparison video')].every(v=>v.readyState>=1));
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 if(step==='source'){assert(document.querySelector('.source-character'),'target reference missing');assert(document.querySelector('.source-character-card figcaption')?.textContent.includes('森林旅人'),'character identity missing');assert(document.querySelector('.source-file-name')?.textContent.includes('原表演'),'source identity missing');}
 else assert(document.querySelectorAll('.swap-comparison > section').length===2,'comparison lost');
 if(step==='source'){
   if(innerWidth<850){document.querySelector('[data-toggle-inspector]').click();await wait(()=>document.querySelector('.inspector-open'));}
   const options=document.querySelector('#property-character .import-options');
   const first=options.children[0].getBoundingClientRect(),second=options.children[1].getBoundingClientRect();
   assert(second.top>=first.bottom,'character imports overlap');assert(second.width>=160,'character import too narrow');
 }
 const state=await fetch('/__fixture/state').then(r=>r.json());assert(state.generation_requests===0,'generation requested');
 document.body.dataset.check=JSON.stringify({passed:true,step,width:innerWidth});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message});}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    class Checked(Handler):
        def do_GET(self):
            if self.path.startswith('/api/v5/prompt-library/pending/'):
                self.send(200,dict(items=[]));return
            if self.path=='/fixture-video.mp4':
                self.send(200,TrackTests.sound.read_bytes(),'video/mp4');return
            super().do_GET()
        def send(self,status,body,content_type='application/json; charset=utf-8'):
            if self.path.startswith('/?') and content_type.startswith('text/html'):body=body.replace(b'</body>',SCRIPT.encode()+b'</body>')
            super().send(status,body,content_type)
    TrackTests.setUpClass()
    fixture=ResultFixture(out);fixture.seed_results()
    p=fixture.projects['fixture-swap']
    source=dict(id='source',kind='video',name='森林中的原表演',url='/fixture-video.mp4')
    character=dict(id='character',kind='image',name='目标角色 · 森林旅人',url='/static/assets/movie/empty-edit.webp')
    p['source_asset']='source';p['asset_library']=[source,character]
    p['segments'][0].update(assets=['character'],resolved_assets=[character],source_file='fixture',source_preview_url='/fixture-video.mp4')
    server=ThreadingHTTPServer(('127.0.0.1',0),Checked);server.fixture=fixture
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        results=[]
        for step in ['source','review']:
            for width,height in [(1366,768),(430,900)]:
                result=capture(f'http://127.0.0.1:{server.server_port}/?step={step}#/p/fixture-swap',out/f'{step}-{width}.png',width,height)
                (out/f'{step}-{width}.html').write_text(result,encoding='utf-8')
                results.append(json.loads(html.unescape(re.search(r'data-check="([^"]+)"',result)[1])))
        (out/'checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        assert all(r['passed'] for r in results),results
    finally:server.shutdown();server.server_close();fixture.close();TrackTests.tearDownClass()

if __name__=='__main__':main()
