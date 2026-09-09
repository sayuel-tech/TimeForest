"""Collection consumes committed snapshots, never current UI text on retry."""
import hashlib
import json
import logging
import threading
import time
import uuid
from pathlib import Path
from .store import Store, encode
from .families import identify


class Library:
    def __init__(self, root, receipts, cfg=None):
        self.root=Path(root); self.receipts=Path(receipts); self.cfg=cfg or {}
        self.lock=threading.RLock(); self._store=None

    @property
    def store(self):
        with self.lock:
            if self._store is None: self._store=Store(self.root)
            return self._store

    def family(self, model, purpose):
        return identify(model,purpose,self.cfg.get('prompt_model_families',[]))

    def context(self, p, target, purpose, settings, scope, content):
        model=settings.get('model') or settings.get('unet') or ''
        family=self.family(model,purpose)
        source=dict(project=p['id'],project_name=p.get('name',''),mode=p.get('mode'),target=target.get('id','project'),
                    scope=scope,recipe=settings.get('recipe'),revision=p.get('revision'),saved_at=p.get('updated_at') or p.get('updated') or time.time(),**family)
        if target.get('prompt_sources'): source['based_on']=target['prompt_sources']
        branches=self.store.branches()
        branch=next((b['id'] for b in branches if b['purpose']==purpose and b['family']==family['family'] and not b.get('deleted_at')),None)
        key=':'.join([p['id'],str(source['target']),scope,family['family'] or 'unknown'])
        row=dict(source_key=key,purpose=purpose,branch=branch,title=(p.get('name','项目')+' · '+str(target.get('name') or ('片段 P%02d'%(target['index']+1) if isinstance(target.get('index'),int) else '当前正文')))[:160],
                    tags=[str(p.get('mode') or purpose),scope],content=content,source=source)
        if p.get('mode')=='swap':
            label={'prompt':'补充说明','swap_custom_prompt':'完整正文','staging':'场景','beats':'节拍'}.get(scope,scope)
            row['title']=(row['title']+' · '+label)[:160]
        return row

    def items(self, p):
        rows=[]
        def add(target,purpose,settings,scope,c):
            if c['type']=='text' and not c['text'].strip(): return
            if c['type']=='fields' and not any(c['fields'].values()): return
            rows.append(self.context(p,target,purpose,settings,scope,c))
        if p.get('mode')=='authoring':
            for entry in p.get('content',{}).get('layers',[]):
                content=entry['content'];scope=entry['layer'];target=dict(id=':'.join(entry['target_ids']) or scope,name=scope)
                if scope=='prompt':
                    payload=content.get('payload',{})
                    if content.get('prompt_mode')=='full':add(target,'video',{'model':'minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors','recipe':content.get('profile_id')},scope,dict(type='text',text=payload.get('prompt_text','')))
                    else:add(target,'video',{'model':'minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors','recipe':content.get('profile_id')},scope,dict(type='fields',fields=payload.get('fields',{}),prompt_mode='structured'))
                elif scope in ('intent','screenplay','asset_screenplay'):
                    text=content.get('story_text') or '\n\n'.join(b.get('text','') for b in content.get('blocks',[]))
                    add(target,'script',{},scope,dict(type='text',text=text))
        elif p.get('kind')=='image' or p.get('mode')=='image':
            for t in p.get('tasks',[]):
                if not t.get('discarded_at'): add(t,'image',t.get('models',{}),t.get('submode','image'),dict(type='text',text=t.get('prompt','')))
        elif p.get('mode')=='video_assembly':
            for clip in p.get('assembly',{}).get('clips',[]):
                if clip.get('removed_at'): continue
                for i,e in enumerate(clip.get('extensions',[])):
                    if not e.get('removed_at'): add({**e,'name':e.get('name') or '续写 '+str(i+1)},'video',e.get('configurations',{}).get(e.get('recipe'),{}),'extension',dict(type='text',text=e.get('prompt','')))
        else:
            settings=p.get('settings',{})
            if p.get('mode')=='swap' and p.get('swap_prompt',{}).get('custom'):
                add(dict(id='project',name='项目默认正文',prompt_sources=p.get('prompt_sources')),'video',settings,'swap_custom_prompt',dict(type='text',text=p['swap_prompt']['custom']))
            for seg in p.get('segments',[]):
                if p.get('mode')=='swap':
                    for field in ('prompt','swap_custom_prompt','staging','beats'):
                        add(seg,'video',settings,field,dict(type='text',text=seg.get(field,'')))
                else:
                    fields={k:seg.get(k,'') for k in ('prompt','staging','beats','ending','voice','soundscape','music','speaker_order')}
                    add(seg,'video',settings,'segment',dict(type='fields',fields=fields,prompt_mode=seg.get('prompt_mode','structured')))
        return rows

    def capture(self, p, identity=None):
        # Persist the exact committed snapshot independently of the library disk.
        snapshot={k:p.get(k) for k in ('id','name','mode','kind','revision','updated_at','updated','settings','swap_prompt','prompt_sources')}
        if p.get('mode')=='authoring':snapshot['content']=p['content']
        if p.get('tasks') is not None:
            snapshot['tasks']=[{k:t.get(k) for k in ('id','name','submode','prompt','models','discarded_at','prompt_sources')} for t in p['tasks']]
        if p.get('segments') is not None:
            keys=('id','name','index','prompt','prompt_mode','staging','beats','ending','voice','soundscape','music','speaker_order','swap_custom_prompt','prompt_sources')
            snapshot['segments']=[{k:t.get(k,'') for k in keys} for t in p['segments']]
        if p.get('assembly'):
            snapshot['assembly']=dict(clips=[dict(removed_at=c.get('removed_at'),extensions=[{k:e.get(k) for k in ('id','name','recipe','configurations','prompt','removed_at','prompt_sources')} for e in c.get('extensions',[])]) for c in p['assembly']['clips']])
        snapshot=json.loads(encode(snapshot))
        token=hashlib.sha256(encode([identity,snapshot]).encode()).hexdigest()
        with self.lock:
            try:
                self.receipts.mkdir(parents=True,exist_ok=True)
                path=self.receipts/(token+'.json')
                if not path.exists():
                    temp=self.receipts/(uuid.uuid4().hex+'.tmp')
                    temp.write_text(encode(dict(project=p['id'],snapshot=snapshot)),encoding='utf-8');temp.replace(path)
                return self.retry(token)
            except Exception as exc:
                logging.getLogger(__name__).warning('Prompt collection pending: %s',exc)
                return dict(state='pending',receipt=token,error=str(exc),retryable=(self.receipts/(token+'.json')).is_file())

    def retry(self, token):
        if not isinstance(token,str) or len(token)!=64 or any(c not in '0123456789abcdef' for c in token): raise ValueError('收录凭据无效')
        with self.lock:
            path=self.receipts/(token+'.json')
            if not path.is_file(): raise KeyError('收录凭据不存在')
            saved=json.loads(path.read_text(encoding='utf-8'))
            if 'snapshot' not in saved: return {**saved['result'],'receipt':token}
            result=self.store.collect('save:'+token,self.items(saved['snapshot']))
            # Retain only a compact receipt after success. A repeated retry is idempotent.
            if 'snapshot' in saved:
                saved=dict(project=saved['project'],result=result)
                temp=path.with_suffix('.tmp');temp.write_text(encode(saved),encoding='utf-8');temp.replace(path)
            return {**result,'receipt':token}

    def pending(self, pid):
        if not self.receipts.exists(): return []
        result=[]
        for path in self.receipts.glob('*.json'):
            row=json.loads(path.read_text(encoding='utf-8'))
            if row.get('project')==pid and 'snapshot' in row: result.append(dict(receipt=path.stem,revision=row['snapshot'].get('revision')))
        return result


def capture(p, identity=None):
    from flask import current_app
    service=current_app.config.get('PROMPT_LIBRARY')
    if service is not None:
        p={**p,'prompt_collection':service.capture(p,identity)}
    return p
