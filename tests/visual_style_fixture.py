"""Static-only font/motion regression probe; no application/configuration/model imports."""
import argparse
import html
import json
import re
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT=Path(__file__).resolve().parents[1]
PAGE='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/static/studio/style.css">
<body class="tf-experience"><main class="page"><div class="project-head"><h1 id="font-heading">时间森林 创作工作台</h1></div><p id="font-body">保存项目，继续编辑人物与场景。Time Forest</p><button id="font-control">保存草稿</button><a class="project-card" style="width:240px"><div class="card-body">项目卡片</div></a><div class="hero-copy">首页入场</div><div class="panel">面板</div><dialog id="dialog" open><div id="dialog-content">对话框</div></dialog></main>
<script>async function check(){await document.fonts.ready;const style=e=>{const s=getComputedStyle(document.querySelector(e));return {family:s.fontFamily,size:s.fontSize,weight:s.fontWeight,transition:s.transitionDuration,animation:s.animationName,animationState:s.animationPlayState}};const sameFonts=style('#font-body').family.includes('Noto Sans SC');document.body.dataset.check=JSON.stringify({passed:sameFonts&&style('#font-heading').weight==='500',body:style('#font-body'),heading:style('#font-heading'),control:style('#font-control'),card:style('.project-card'),panel:style('.panel'),reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,hidden:document.hidden,fonts:[...document.fonts].filter(f=>f.status==='error').map(f=>f.family)});}check();</script>'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--literal',action='store_true');parser.add_argument('--reduced',action='store_true');args=parser.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
        def do_GET(self):
            if urlparse(self.path).path=='/style-probe':
                page=PAGE
                if args.literal:page=page.replace('<body','<style>body{font:15px/1.7 var(--sans)}</style><body')
                data=page.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(data);return
            return super().do_GET()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        result=subprocess.run([sys.executable,str(ROOT/'tests/uiux_browser_capture.py'),f'http://127.0.0.1:{server.server_port}/style-probe?reduced={int(args.reduced)}',str(out/'page.png'),'1366','768'],capture_output=True,timeout=60)
        dom=result.stdout.decode('utf-8','replace');(out/'page.html').write_text(dom,encoding='utf-8');match=re.search(r'data-check="([^"]+)"',dom)
        data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error=result.stderr.decode('utf-8','replace'))
        motion=json.loads((out/'page.motion.json').read_text(encoding='utf-8'));data['motion']=motion
        motion_ok=(motion['hero']=='none' and motion['dialog']=='none' and all(float(x.strip().removesuffix('s'))==0 for x in motion['button'].split(','))) if args.reduced else (motion['hero']=='panel-in' and motion['dialog']=='panel-in' and motion['transform']=='matrix(1, 0, 0, 1, 0, -3)' and motion['shadow']!='none')
        data['passed']=data['passed'] and motion_ok
        if not data['passed']:data['error']='Original type roles require heading weight 500 and Noto Sans body'
        (out/'checks.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data,ensure_ascii=False))
        if not data['passed']:raise SystemExit(1)
    finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
