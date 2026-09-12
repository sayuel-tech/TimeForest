"""Text story UI, controlled API/media fixtures; no production or generation."""
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
const pause=()=>new Promise(r=>setTimeout(r,70)),assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async f=>{for(let i=0;i<200;i++){if(await f())return;await pause();}throw Error('timeout '+f)};
const click=async s=>{document.querySelector(s).click();await pause()};
const get=()=>fetch('/api/v5/projects/fixture-text-story').then(r=>r.json());
const control=body=>fetch('/__fixture/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
try{
 const {shotPrompt}=await import('/static/studio/features/prompts/authoring.js');
 for(const mode of ['text_story','image_story']){for(const text of ['', '\n正文', '\n\n正文', '正文']){const root=document.createElement('div');root.innerHTML=shotPrompt({project:{mode}}, {id:'probe',index:0,prompt:text});assert(root.querySelector('textarea').value===text,'HTML whitespace roundtrip '+mode);}}
 const step=new URLSearchParams(location.search).get('step');
 await wait(()=>document.querySelector('textarea[data-field="prompt"]'));
 const input=()=>document.querySelector('textarea[data-field="prompt"]'),desk=()=>document.querySelector('.text-desk');
 assert(desk().classList.contains('inspector-collapsed'),'initial sidebar consumes writing area');
 const initial=input(),first=initial.value,revision=(await get()).revision;
 assert(step==='empty'?first==='':first.length>600,'wrong initial prose');
 const edited=first+'\n补充：镜头停留在人物望向远处的瞬间。';initial.value=edited;initial.dispatchEvent(new Event('input',{bubbles:true}));
 initial.focus();initial.setSelectionRange(12,12);initial.scrollTop=60;const scroll=initial.scrollTop;
 const toggle=document.querySelector('[data-toggle-inspector]');toggle.scrollIntoView({block:'nearest'});
 const rect=toggle.getBoundingClientRect(),hit=document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2);
 assert(toggle===hit||toggle.contains(hit),'sidebar toggle covered');
 await click('[data-toggle-inspector]');
 assert(input()===initial&&input().value===edited&&input().selectionStart===12,'sidebar replaced input or caret');
 if(innerWidth>=1180)assert(!desk().classList.contains('inspector-collapsed'),'sidebar did not open');
 else assert(desk().classList.contains('inspector-open'),'drawer did not open');
 await click('[data-property-tab="sound"]');const voice=document.querySelector('[data-field="voice"]');voice.value='轻声，保留呼吸。';voice.dispatchEvent(new Event('input',{bubbles:true}));
 if(innerWidth<1180)await click('[data-close-inspector]');else await click('[data-toggle-inspector]');
 assert(input()===initial&&input().scrollTop===scroll,'close lost editor or scroll');
 assert((await get()).revision===revision,'toggle implicitly saved');
 if(innerWidth<850)await click('[data-toggle-directory]');
 await click('[data-focus-shot="1"]');assert(input().value.includes('灯塔'),'wrong second segment');
 if(innerWidth<850)await click('[data-close-directory]');
 if(innerWidth<850)await click('[data-toggle-directory]');
 await click('[data-focus-shot="0"]');assert(input().value===edited,'switch lost draft: '+JSON.stringify({expected:edited,actual:input().value}));
 if(innerWidth<850)await click('[data-close-directory]');
 await control({save_error:true});await click('[data-workspace-step="review"]');
 await wait(()=>document.querySelector('#toast')?.textContent.includes('冲突'));
 assert(input()?.value===edited&&(await get()).segments[0].prompt===first,'failed save lost draft or advanced');
 await control({save_error:false});await click('#save');await wait(async()=>(await get()).segments[0].prompt===edited);
 assert((await get()).segments[0].voice==='轻声，保留呼吸。','voice lost');
 if(step==='review'){
  await click('[data-workspace-step="review"]');await wait(()=>document.querySelector('.script-prose'));
  const prose=document.querySelector('.script-prose');assert(prose.textContent===edited,'review not current prose');
  assert(document.querySelector('.script-review-copy h3').textContent.includes('P01'),'review identity');
  assert(parseFloat(getComputedStyle(prose).fontSize)>=16,'review body too small');
  prose.focus();prose.scrollTop=prose.scrollHeight;assert(prose.scrollTop+prose.clientHeight>=prose.scrollHeight-2,'ending unreachable');prose.scrollTop=0;
  await wait(()=>document.querySelector('.script-review video')?.readyState>=1);
 }else{
  assert(parseFloat(getComputedStyle(input()).fontSize)>=16&&input().clientHeight>=160,'writing unreadable');
  input().scrollTop=input().scrollHeight;assert(input().scrollTop+input().clientHeight>=input().scrollHeight-2,'full editor unreachable');input().scrollTop=0;
 }
 await document.fonts.ready;await pause();
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 const state=await fetch('/__fixture/state').then(r=>r.json());assert(state.generation_requests===0,'generation requested');
 document.body.dataset.check=JSON.stringify({passed:true,step,width:innerWidth,checks:['empty/long prose','sidebar DOM caret scroll','voice save','segment switching','failed save blocks review','save roundtrip','full ending','no generation']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack});}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--cases',default='empty,edit,review');parser.add_argument('--widths',default='1366,430');args=parser.parse_args()
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
    p=fixture.projects['fixture-text-story']
    from tests.readability_ui_fixture import BODY, PROMPTS
    p['segments'][0].update(prompt=PROMPTS[0][1]+BODY)
    second=copy.deepcopy(p['segments'][0]);second.update(id='second-shot',index=1,prompt='灯塔旁的新场景，人物望向海面。')
    p['segments'].append(second);p['duration']=30
    server=ThreadingHTTPServer(('127.0.0.1',0),Checked);server.fixture=fixture
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        results=[]
        original=copy.deepcopy(p)
        for step in args.cases.split(','):
            for width,height in [(1366,768),(430,900)]:
                if str(width) not in args.widths.split(','): continue
                fixture.projects[p['id']]=copy.deepcopy(original)
                if step=='empty': fixture.projects[p['id']]['segments'][0]['prompt']=''
                result=capture(f'http://127.0.0.1:{server.server_port}/?step={step}#/p/fixture-text-story',out/f'{step}-{width}.png',width,height)
                (out/f'{step}-{width}.html').write_text(result,encoding='utf-8')
                results.append(json.loads(html.unescape(re.search(r'data-check="([^"]+)"',result)[1])))
        (out/'checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        assert all(r['passed'] for r in results),results
    finally:server.shutdown();server.server_close();fixture.close();TrackTests.tearDownClass()

if __name__=='__main__':main()
