"""Capture an isolated fixture at an exact CSS viewport with the installed Chrome.

Only loopback fixture URLs are accepted; this never opens the production website.
Chrome uses its own temporary profile and exits after the fixture's completion marker.
"""
import argparse
import base64
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import websocket


def capture(url, output, width, height):
    assert urlparse(url).hostname == '127.0.0.1', 'Only isolated loopback fixtures'
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='tf-uiux-browser-') as profile:
        process = subprocess.Popen([
            'C:/Program Files/Google/Chrome/Application/chrome.exe', '--headless=new',
            '--disable-gpu', '--no-first-run', '--disable-background-networking',
            '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank',
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        connection = None
        try:
            port_file = Path(profile) / 'DevToolsActivePort'
            deadline = time.monotonic() + 15
            while True:
                try:
                    port = int(port_file.read_text().splitlines()[0])
                    break
                except (FileNotFoundError, PermissionError, IndexError, ValueError):
                    if time.monotonic() > deadline:
                        raise TimeoutError('Chrome startup')
                    time.sleep(.05)
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list') as response:
                targets = json.load(response)
            target = next(t for t in targets if t['type'] == 'page')
            connection = websocket.create_connection(target['webSocketDebuggerUrl'],
                                                      suppress_origin=True, timeout=15)
            serial = 0

            def command(method, params=None):
                nonlocal serial
                serial += 1
                connection.send(json.dumps(dict(id=serial, method=method, params=params or {})))
                while True:
                    message = json.loads(connection.recv())
                    if message.get('id') == serial:
                        if 'error' in message:
                            raise RuntimeError(message['error'])
                        return message.get('result', {})

            command('Page.enable')
            command('Emulation.setDeviceMetricsOverride', dict(width=width, height=height,
                    deviceScaleFactor=1, mobile=False))
            if 'style-probe' in url:command('Emulation.setEmulatedMedia',dict(features=[dict(name='prefers-reduced-motion',value='reduce' if 'reduced=1' in url else 'no-preference')]))
            command('Page.navigate', dict(url=url))
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                stroke = command('Runtime.evaluate', dict(expression='document.body?.dataset.pointerStroke', returnByValue=True))
                if stroke.get('result', {}).get('value') == 'requested':
                    rect = command('Runtime.evaluate', dict(expression='(()=>{const c=document.querySelector("canvas"),r=c.getBoundingClientRect();return {x:r.left+r.width*.12,y:r.top+r.height*.12}})()', returnByValue=True))['result']['value']
                    command('Input.dispatchMouseEvent', dict(type='mouseMoved', **rect))
                    command('Input.dispatchMouseEvent', dict(type='mousePressed', button='left', clickCount=1, **rect))
                    command('Input.dispatchMouseEvent', dict(type='mouseMoved', x=rect['x']+20, y=rect['y']+10, buttons=1))
                    command('Input.dispatchMouseEvent', dict(type='mouseReleased', x=rect['x']+20, y=rect['y']+10, button='left', clickCount=1))
                    command('Runtime.evaluate', dict(expression='document.body.dataset.pointerStroke="done"'))
                result = command('Runtime.evaluate', dict(
                    expression='document.body?.dataset.check || ""', returnByValue=True))
                if result.get('result', {}).get('value'):
                    break
                time.sleep(.1)
            command('Runtime.evaluate', dict(expression='document.fonts.ready', awaitPromise=True))
            # Let a genuine transient save receipt finish before recording the resting page.
            deadline = time.monotonic() + 5.5
            while time.monotonic() < deadline:
                toast = command('Runtime.evaluate', dict(expression='document.querySelector("#toast")?.classList.contains("show")', returnByValue=True))
                if not toast.get('result', {}).get('value'):
                    break
                time.sleep(.1)
            if 'style-probe' in url:
                command('DOM.enable');command('CSS.enable')
                document = command('DOM.getDocument')['root']['nodeId'];fonts = {}
                for selector in ['#font-body','#font-heading','#font-control']:
                    node = command('DOM.querySelector',dict(nodeId=document,selector=selector))['nodeId']
                    fonts[selector] = command('CSS.getPlatformFontsForNode',dict(nodeId=node))['fonts']
                output.with_suffix('.fonts.json').write_text(json.dumps(fonts,ensure_ascii=False,indent=2),encoding='utf-8')
                card=command('DOM.querySelector',dict(nodeId=document,selector='.project-card'))['nodeId']
                command('CSS.forcePseudoState',dict(nodeId=card,forcedPseudoClasses=['hover']))
                command('Runtime.evaluate',dict(expression='new Promise(r=>setTimeout(r,300))',awaitPromise=True))
                motion=command('Runtime.evaluate',dict(expression='(()=>{const c=getComputedStyle(document.querySelector(".project-card")),h=getComputedStyle(document.querySelector(".hero-copy")),d=getComputedStyle(document.querySelector("dialog")),b=getComputedStyle(document.querySelector("button"));return {transform:c.transform,shadow:c.boxShadow,transition:c.transitionDuration,hero:h.animationName,dialog:d.animationName,button:b.transitionDuration,reduced:matchMedia("(prefers-reduced-motion: reduce)").matches}})()',returnByValue=True))['result']['value']
                output.with_suffix('.motion.json').write_text(json.dumps(motion,ensure_ascii=False,indent=2),encoding='utf-8')

            screenshot = command('Page.captureScreenshot', dict(format='png', captureBeyondViewport=False))
            output.write_bytes(base64.b64decode(screenshot['data']))
            result = command('Runtime.evaluate', dict(expression='document.documentElement.outerHTML', returnByValue=True))
            return result['result']['value']
        finally:
            if connection:
                connection.close()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('output')
    parser.add_argument('width', type=int)
    parser.add_argument('height', type=int)
    args = parser.parse_args()
    print(capture(args.url, args.output, args.width, args.height))
