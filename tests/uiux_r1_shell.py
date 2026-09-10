"""Use the real application shell and ES modules with the existing isolated fixtures."""
import re
from pathlib import Path


def application_shell(page, root_id="root"):
    shell = (Path(__file__).resolve().parents[1] / 'static/index.html').read_text(encoding='utf-8')
    shell = re.sub(r'<script type="module" src="[^"]+"></script>', '', shell)
    shell = shell.replace('id="app"', f'id="{root_id}"')
    scripts = ''.join(re.findall(r'<script\b[^>]*>[\s\S]*?</script>', page))
    initialization = '''<script type="module">
import {mountSiteNavigation} from '/static/studio/ui/site-navigation.js';
const fixtureId=new URLSearchParams(location.search).get('pid');
if(fixtureId)history.replaceState(null,'','#/p/'+fixtureId);
mountSiteNavigation(document.querySelector('#root'));
window.addEventListener('error',e=>document.body.dataset.check=JSON.stringify({passed:false,error:e.message}));
window.addEventListener('unhandledrejection',e=>document.body.dataset.check=JSON.stringify({passed:false,error:String(e.reason)}));
</script>'''
    return shell.replace('</body>', initialization.replace("querySelector('#root')", "querySelector('#"+root_id+"')") + scripts + '</body>')
