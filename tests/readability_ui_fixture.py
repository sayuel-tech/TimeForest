"""Finite reading tasks on the real prompt/asset libraries; temporary data only."""
import json, sys, threading
from pathlib import Path
from werkzeug.serving import make_server, WSGIRequestHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_prompt_library import PromptLibraryTests
from tests.workspace_navigation_ui_fixture import capture

PROMPTS = [
    ('雨后车站 · 寻找没有寄出的信', '车站刚下过雨。人物站在站台遮雨棚下，将一封没有寄出的信拿在手里。远处列车驶来，她没有立即上前，而是先看了一眼信封上的地址。'),
    ('海边清晨 · 潮水退去以后', '清晨的海岸没有游客。人物沿潮水退去后的湿沙前行，蹲下查看一枚贝壳，再抬头望向远处的灯塔。这个片段强调等待之后重新出发的情绪。'),
    ('山间归途 · 天黑前的最后一段路', '人物背着帆布包穿过山间小路。路边的草叶带着露水，前方木屋的灯刚刚亮起。她放慢脚步，整理肩带，再继续向木屋走去。'),
    ('旧书店 · 午后的访客', '午后的书店只有一位访客。她取下书架上一册磨损的旧书，翻到夹着明信片的一页。窗外有人骑车经过，窗框的阴影缓缓移动。'),
]
BODY = '''

镜头与动作：先用中景交代人物和环境的位置关系，再以缓慢的侧向移动跟随人物。镜头保持视线高度，避免突兀推近。人物的动作需要有停顿和呼吸，不要连续做出多个没有动机的手势。每一次转头都应有明确的观察对象。

人物与服装：沿用参考图片中的五官、发型、灰绿色外套和帆布包。衣服随动作自然起伏，保持同一人物与同一套服装。手里的物品始终在同一只手中，另一只手偶尔整理肩带；进入近景时仍保留原有的空间方向。

光线与色彩：阴影保留细节，背景色彩略低饱和。人物肤色自然，不增加美颜、发光轮廓或高对比锐化。使用 soft natural light 与 subtle film grain 的质感，但不要让颗粒遮住面部细节。高光保持柔和，不出现镜头光晕。

声音与节奏：环境声随镜头位置变化，近处能听到衣料摩擦与脚步，远处只保留轻微的城市或自然底噪。没有旁白，没有人物说话。音乐如果出现，应在片尾缓慢进入，音量低于环境声，不主导人物表演。

参考与连续性：参考素材只提供人物形象与环境色彩，不能把参考图中的边框、文字或拼贴结构带入成片。人物在画面中的位置应与上一个片段一致，远处建筑和道路保持相对关系。镜头缓慢前移时，背景产生自然的视差，不要让场景像平面照片一样整体滑动。光源方向始终一致。

结尾约束：最后两秒保留人物继续前行的动作，画面不能突然静止或淡出。延续同一方向和镜头高度，为后续片段留出动作余量。不要在结尾添加字幕、标题、标志或新的角色。【全文结束：保留续接方向】'''

SCRIPT = r'''<script type="module">
import {pickPrompt} from '/static/studio/features/prompt-library/tools.js';
import {mountPromptLibrary} from '/static/studio/pages/prompt-library/index.js';
import {mountLibrary} from '/static/studio/pages/asset-library/index.js';
import {pickLibraryAsset} from '/static/studio/features/asset-picker/index.js';
const root=document.querySelector('#app'),view=new URLSearchParams(location.search).get('view'),controller=new AbortController();
const assert=(v,m)=>{if(!v)throw Error(m)},pause=()=>new Promise(r=>setTimeout(r,50)),wait=async(fn)=>{for(let i=0;i<180;i++){if(fn())return;await pause()}throw Error('timeout '+fn)};
const checks=[];
try{
 if(view==='asset-preview'){
  let picked=false;void pickLibraryAsset({signal:controller.signal}).then(v=>picked=!!v);
  await wait(()=>document.querySelector('[data-preview]'));const details=document.querySelector('[data-preview]');details.open=true;
  await wait(()=>details.querySelector('img'));await pause();
  assert(details.getBoundingClientRect().width>document.querySelector('.library-picker-results').clientWidth*.9,'preview still confined to thumbnail card');
  assert(!picked,'preview selected asset');checks.push('whole-row media preview without selection');
 }else if(view==='asset-notes'){
  const list=await fetch('/api/v5/library/assets').then(r=>r.json());const before=await fetch('/api/v5/library/assets/'+list.items[0].id).then(r=>r.json());
  await mountLibrary(root,'#/assets/'+before.id,controller.signal);root.querySelector('.reading-expand').click();await wait(()=>document.querySelector('[data-expanded]'));
  const input=document.querySelector('[data-expanded]'),text=input.value;assert(text.length>600,'missing long notes');input.value='cancel me';document.querySelector('[data-cancel]').click();await pause();
  assert(root.querySelector('[name=record_prompt]').value===text,'cancel changed asset draft');
  root.querySelector('.reading-expand').click();await wait(()=>document.querySelector('[data-expanded]'));document.querySelector('[data-expanded]').value=text+'\n本机修改';document.querySelector('[data-apply]').click();await pause();
  assert(root.querySelector('[name=record_prompt]').value.endsWith('本机修改'),'expanded edit not returned to draft');
  const after=await fetch('/api/v5/library/assets/'+before.id).then(r=>r.json());assert(before.revision===after.revision,'expanded edit saved asset');
  root.querySelector('.reading-expand').click();await wait(()=>document.querySelector('[data-expanded]'));checks.push('long asset notes/cancel/apply to draft/no library write');
 }else{
  let choice=null;
  if(view==='management')await mountPromptLibrary(root,controller.signal);
  else void pickPrompt({purpose:'video',signal:controller.signal}).then(v=>choice=v);
  await wait(()=>document.querySelector('[data-branch="video:h3"]'));
  document.querySelector('[data-branch="video:h3"]').click();await wait(()=>document.querySelectorAll('[data-entry]').length===4);
  const entries=[...document.querySelectorAll('[data-entry]')],list=document.querySelector('[data-list]');
  assert(entries[0].getBoundingClientRect().width>list.closest('.prompt-library-browser').clientWidth*.65,'list does not own main area');
  assert(new Set(entries.map(e=>e.querySelector('span').textContent)).size===4,'summaries not distinct');
  if(view!=='list'){
   entries[1].scrollIntoView({block:'center'});const dialog=entries[1].closest('dialog'),savedScroll=dialog?dialog.scrollTop:window.scrollY;
   entries[1].click();const frame=document.querySelector('.prompt-library-browser'),text=document.querySelector('[data-detail]>.prompt-text');
   assert(frame.dataset.view==='read'&&document.querySelector('.prompt-results').hidden,'list still competes with reading');
   assert(text.textContent.length>600&&text.textContent.endsWith('【全文结束：保留续接方向】'),'full prompt missing');
   assert(parseFloat(getComputedStyle(text).fontSize)>=16&&getComputedStyle(text).maxHeight==='none','reading font/height wrong');
   assert(text.getBoundingClientRect().width>Math.min(560,innerWidth*.7),'reading too narrow');
   const copy=text.textContent,id=entries[1].dataset.entry;document.querySelector('[data-read-next]').click();assert(document.querySelector('[data-detail]>.prompt-text').textContent!==copy,'next same prompt');
   document.querySelector('[data-read-prev]').click();assert(document.querySelector('[data-detail]>.prompt-text').textContent===copy,'previous lost prompt');
   document.querySelector('[data-back-list]').click();assert(!document.querySelector('.prompt-results').hidden&&list.contains(entries[1]),'back rebuilt list');
   assert(document.activeElement===entries[1]&&Math.abs((dialog?dialog.scrollTop:window.scrollY)-savedScroll)<3,'back lost focus/scroll');
   assert(document.querySelector('[data-path]').textContent==='视频 / H3','back lost category');entries[1].click();
   const action=document.querySelector('[data-use]');if(action){action.scrollIntoView({block:'center'});assert(action.getBoundingClientRect().bottom<=innerHeight,'apply unreachable');action.click();await wait(()=>choice);assert(choice.id===id&&choice.content.text===copy,'wrong selected body');void pickPrompt({purpose:'video',signal:controller.signal});await wait(()=>document.querySelector('[data-branch="video:h3"]'));document.querySelector('[data-branch="video:h3"]').click();await wait(()=>document.querySelectorAll('[data-entry]').length===4);document.querySelectorAll('[data-entry]')[1].click();}
   checks.push('600+ characters/full ending/next-previous/back preserves DOM filters scroll focus/exact selection');
  }else checks.push('distinct readable summaries/no empty detail column');
 }
 await document.fonts.ready;await pause();await pause();window.scrollTo({top:0,behavior:'instant'});const d=document.querySelector('dialog[open]');if(d)d.scrollTop=0;
 assert(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');if(d)assert(d.scrollWidth<=d.clientWidth+1,'dialog overflow');
 document.body.dataset.check=JSON.stringify({passed:true,view,width:innerWidth,checks});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,view,error:e.stack});}
</script>'''

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);case=PromptLibraryTests();case.setUp();checks=[]
    for title,intro in PROMPTS:
        case.post('/prompt-library/entries',dict(title=title,purpose='video',branch='video:h3',content=dict(type='text',text=intro+BODY)))
    lib=case.app.config['ASSET_LIBRARY']
    for i,image in enumerate(Path('static/assets/modes').glob('*.webp')):
        lib.ingest(image,'林间旅程的角色、场景与色彩参考 · '+str(i),metadata={'record_prompt':PROMPTS[0][1]+BODY,'description':BODY,'categories':['scene']})
    page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="app" class="page"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
    def app(env,start):
        if env['PATH_INFO']=='/reading-check':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
        return case.app(env,start)
    class Quiet(WSGIRequestHandler):
        def log(self,*a,**k):pass
    server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        views=next((a.split('=',1)[1].split(',') for a in sys.argv if a.startswith('--views=')),['list','read','management','asset-preview','asset-notes'])
        for width in [1280,760]:
            for view in views:
                checks.append(capture(out,f'{view}-{width}',f'http://127.0.0.1:{server.server_port}/reading-check?view={view}',width))
    finally:server.shutdown();server.server_close();case.doCleanups()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)
if __name__=='__main__':main()
