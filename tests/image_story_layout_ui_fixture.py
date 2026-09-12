"""Reference story UI, controlled API/media fixtures; no production or generation."""
import copy
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

SCRIPT=r'''<script type="module">
const pause=()=>new Promise(r=>setTimeout(r,60));
const wait=async f=>{for(let i=0;i<200;i++){if(await f())return;await pause();}throw Error('UI timeout: '+f);};
const assert=(v,m)=>{if(!v)throw Error(m)};
const click=async s=>{document.querySelector(s).click();await pause();};
const get=()=>fetch('/api/v5/projects/fixture-image-story').then(r=>r.json());
const control=body=>fetch('/__fixture/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
try{
 const step=new URLSearchParams(location.search).get('step');
 await wait(()=>document.querySelector('[data-workspace-step="edit"]'));
 await click('[data-workspace-step="edit"]');
 const prompt=()=>document.querySelector('textarea[data-field="prompt"]');
 await wait(()=>prompt());
 const first=prompt().value,changed=first+'\n本段补充：向林间走去。';
 assert(first.length>600,'missing long prose');
 const disclosure=document.querySelector('.image-story-references');
 assert(!disclosure.open,'references compete with initial writing');
 const style=getComputedStyle(prompt());
 assert(parseFloat(style.fontSize)>=16&&prompt().clientHeight>=160,'prose unreadable');
 prompt().value=changed;prompt().dispatchEvent(new Event('input',{bubbles:true}));
 await click('.image-story-references > summary');
 assert(prompt().value===changed,'expand lost draft');
 assert(document.querySelector('.reference-contact-sheet figcaption').textContent.includes('森林旅人'),'first reference identity');
 await click('[data-focus-shot="1"]');
 assert(prompt().value.includes('灯塔'),'second prose mismatch');
 assert(document.querySelector('.image-story-references summary').textContent.includes('P02'),'second identity');
 assert(document.querySelector('.reference-contact-sheet figcaption').textContent.includes('森林旅人'),'auto did not inherit P1');
 const change=async v=>{const el=document.querySelector('[data-asset-mode]');el.value=v;el.dispatchEvent(new Event('change',{bubbles:true}));await pause();};
 await change('custom');assert(!document.querySelector('.reference-contact-sheet figure'),'custom borrowed P1');
 await change('none');assert(!document.querySelector('.reference-contact-sheet figure'),'none retained picture');
 assert(!document.querySelector('.reference-contact-sheet').textContent.includes('继续上一段'),'none claims continuity');
 await change('auto');
 await click('[data-focus-shot="0"]');assert(prompt().value===changed,'switch lost first draft');
 await control({save_error:true});await click('[data-workspace-step="review"]');
 await wait(()=>document.querySelector('#toast')?.textContent.includes('冲突'));
 assert(prompt()?.value===changed,'save failure lost draft or advanced');
 assert((await get()).segments[0].prompt===first,'failed save wrote');
 await control({save_error:false});await click('#save');
 await wait(async()=>(await get()).segments[0].prompt===changed);
 if(step==='review'){
  await click('[data-workspace-step="review"]');await wait(()=>document.querySelector('.image-review'));
  assert(document.querySelector('.reference-rail h3').textContent.includes('P01'),'review object identity');
  assert(document.querySelector('.reference-rail figcaption').textContent.includes('森林旅人'),'review name');
  await wait(()=>document.querySelector('.image-review video')?.readyState>=1);
 }else{document.querySelector('.image-story-references').open=false;}
 await document.fonts.ready;await pause();
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 const state=await fetch('/__fixture/state').then(r=>r.json());assert(state.generation_requests===0,'generation requested');
 document.body.dataset.check=JSON.stringify({passed:true,step,width:innerWidth,checks:['long prose','reference identity','segment draft isolation','auto/custom/none','expand retains draft','save failure blocks navigation','save roundtrip','no generation']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack});}
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
    p=fixture.projects['fixture-image-story']
    character=dict(id='character',kind='image',name='角色参考 · 森林旅人与灰绿色外套',url='/static/assets/movie/empty-edit.webp')
    p['asset_library']=[character]
    p['segments'][0].update(assets=['character'],prompt=('森林旅人沿着石阶行走，留意树间洒下的光。镜头缓慢前行，保留外套与肩包的细节。环境里只有树叶与脚步声。\n'*16))
    second=copy.deepcopy(p['segments'][0]);second.update(id='second-shot',index=1,assets=[],asset_mode='auto',head=0,boundary='new_scene',prompt='灯塔旁的新场景，人物望向海面。')
    p['segments'].append(second);p['duration']=30
    server=ThreadingHTTPServer(('127.0.0.1',0),Checked);server.fixture=fixture
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        results=[]
        original=copy.deepcopy(p)
        for step in ['edit','review']:
            for width,height in [(1366,768),(430,900)]:
                fixture.projects[p['id']]=copy.deepcopy(original)
                result=capture(f'http://127.0.0.1:{server.server_port}/?step={step}#/p/fixture-image-story',out/f'{step}-{width}.png',width,height)
                (out/f'{step}-{width}.html').write_text(result,encoding='utf-8')
                results.append(json.loads(html.unescape(re.search(r'data-check="([^"]+)"',result)[1])))
        (out/'checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        assert all(r['passed'] for r in results),results
    finally:server.shutdown();server.server_close();fixture.close();TrackTests.tearDownClass()

if __name__=='__main__':main()
