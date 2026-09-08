"""Versioned prompt storage. All writes use optimistic revisions and transactions."""
import copy
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from ..studio_store import Conflict

PURPOSES = {'video': '视频', 'image': '图片', 'script': '剧本'}
FIELDS = {'prompt','staging','beats','ending','voice','soundscape','music','speaker_order','swap_custom_prompt'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def content(value):
    if not isinstance(value, dict) or value.get('type') not in ('text', 'fields'):
        raise ValueError('提示词内容格式无效')
    if value['type'] == 'text':
        if not isinstance(value.get('text'), str) or not value['text'].strip():
            raise ValueError('请填写提示词')
        result = dict(type='text', text=value['text'])
    else:
        fields = value.get('fields')
        if not isinstance(fields, dict) or not fields or set(fields)-FIELDS or any(not isinstance(v,str) for v in fields.values()):
            raise ValueError('字段组合无效')
        if not any(v.strip() for v in fields.values()): raise ValueError('请填写提示词')
        result = dict(type='fields', fields=fields, prompt_mode=value.get('prompt_mode','structured'))
        if result['prompt_mode'] not in ('structured','full'): raise ValueError('正文方式无效')
    if len(encode(result)) > 500000: raise ValueError('提示词内容过长，请分条保存')
    return result


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root/'prompts.sqlite3'
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS branches(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, source_key TEXT UNIQUE, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions(entry TEXT, version INTEGER, body TEXT NOT NULL, PRIMARY KEY(entry,version));
            CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            ''')
            for purpose in PURPOSES:
                for family, name in [('general','通用')] + ([('h3','H3')] if purpose=='video' else [('krea2','Krea2')] if purpose=='image' else []):
                    row=dict(id=purpose+':'+family,purpose=purpose,family=family,name=name,system=True,revision=1,position=0 if family=='general' else 1,deleted_at=None)
                    db.execute('INSERT OR IGNORE INTO branches VALUES(?,?)',(row['id'],encode(row)))

    @contextmanager
    def connect(self, write=False):
        db=sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                if write: db.execute('BEGIN IMMEDIATE')
                yield db
        finally: db.close()

    def _get(self, db, table, ident):
        row=db.execute(f'SELECT body FROM {table} WHERE id=?',(ident,)).fetchone()
        if not row: raise KeyError('记录不存在')
        return json.loads(row[0])

    def branches(self):
        with self.connect() as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM branches')]
            counts={}
            for (body,) in db.execute('SELECT body FROM entries'):
                branch=json.loads(body).get('branch');counts[branch]=counts.get(branch,0)+1
            for row in rows:row['entry_count']=counts.get(row['id'],0)
        return sorted(rows,key=lambda r:(r['purpose'],r['position'],r['name']))

    def branch(self, data, ident=None):
        with self.connect(True) as db:
            old=self._get(db,'branches',ident) if ident else None
            if old and old['revision']!=data.get('revision'): raise Conflict('分类已更新，请重新打开后修改')
            purpose=old['purpose'] if old else data.get('purpose')
            if purpose not in PURPOSES: raise ValueError('用途无效')
            name=str(data.get('name',old['name'] if old else '')).strip()
            if not name or len(name)>80: raise ValueError('分类名称须为1～80字')
            removed=data.get('removed',bool(old and old.get('deleted_at')))
            if old and old['system'] and removed: raise ValueError('通用和当前工作流家族不能移除')
            family=old['family'] if old else str(data.get('family') or uuid.uuid4().hex)
            if not family or len(family)>80: raise ValueError('家族标识无效')
            for row in db.execute('SELECT body FROM branches'):
                b=json.loads(row[0])
                if b['id']!=ident and b['purpose']==purpose and (b['name']==name or b['family']==family):
                    raise Conflict('同用途已有此名称或家族，包括回收站分类')
            value=dict(id=ident or uuid.uuid4().hex,purpose=purpose,family=family,name=name,system=bool(old and old['system']),
                       revision=(old['revision'] if old else 0)+1,position=int(data.get('position',old['position'] if old else 10)),deleted_at=(old.get('deleted_at') or time.time()) if removed else None)
            db.execute('INSERT OR REPLACE INTO branches VALUES(?,?)',(value['id'],encode(value)))
            return value

    def _validate_branch(self, db, purpose, branch, allow_removed=False):
        if purpose not in PURPOSES: raise ValueError('用途无效')
        if branch is None: return
        row=self._get(db,'branches',branch)
        if row['purpose']!=purpose: raise ValueError('模型分支不属于当前用途')
        if row.get('deleted_at') and not allow_removed: raise ValueError('请先恢复或选择可用分类')

    def get(self, ident, version=None):
        with self.connect() as db:
            row=self._get(db,'entries',ident)
            if version is not None:
                saved=db.execute('SELECT body FROM versions WHERE entry=? AND version=?',(ident,int(version))).fetchone()
                if not saved: raise KeyError('内容版本不存在')
                row={**row,**json.loads(saved[0])}
            return row

    def versions(self, ident):
        with self.connect() as db:
            self._get(db,'entries',ident)
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM versions WHERE entry=? ORDER BY version DESC',(ident,))]

    def list(self, filters):
        branches={b['id']:b for b in self.branches()}
        with self.connect() as db: rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM entries')]
        result=[]
        for row in rows:
            removed=bool(row.get('deleted_at') or branches.get(row.get('branch'),{}).get('deleted_at'))
            if removed != (filters.get('trash')=='1'): continue
            if filters.get('purpose') and row['purpose']!=filters['purpose']: continue
            if filters.get('branch') and row.get('branch')!=filters['branch']: continue
            if filters.get('unclassified')=='1' and row.get('branch') is not None: continue
            if filters.get('favorite')=='1' and not row['favorite']: continue
            if filters.get('kind') and row['record_kind']!=filters['kind']: continue
            if filters.get('q','').casefold() not in (row['title']+' '+encode(row['content'])+' '+ ' '.join(row['tags'])).casefold(): continue
            result.append(row)
        result.sort(key=lambda r:r['updated_at'],reverse=True)
        offset=max(0,int(filters.get('offset',0))); limit=min(100,max(1,int(filters.get('limit',50))))
        return dict(items=result[offset:offset+limit],total=len(result),offset=offset,limit=limit)

    def _save(self, db, data, ident=None, source_key=None, automatic=False):
        old=self._get(db,'entries',ident) if ident else None
        if old and not automatic and data.get('revision')!=old['revision']: raise Conflict('提示词已被其他页面修改，请重新打开；当前文字保留')
        c=content(data.get('content',old['content'] if old else None))
        if old and old['record_kind']=='automatic' and not automatic and c!=old['content']:
            raise ValueError('创作记录不能改写，请另存为模板')
        purpose=data.get('purpose',old['purpose'] if old else None)
        branch=data.get('branch',old['branch'] if old else None)
        self._validate_branch(db,purpose,branch,allow_removed=bool(old and branch==old['branch']))
        if c['type']=='fields' and purpose!='video': raise ValueError('此字段组合仅适用于视频，请另存所需文字')
        title=str(data.get('title',old['title'] if old else '')).strip()
        if not title or len(title)>160: raise ValueError('标题须为1～160字')
        tags=data.get('tags',old['tags'] if old else [])
        if not isinstance(tags,list) or len(tags)>30 or any(not isinstance(t,str) or len(t)>80 for t in tags): raise ValueError('标签格式无效')
        now=time.time(); changed=not old or c!=old['content']
        row=dict(id=ident or uuid.uuid4().hex,purpose=purpose,branch=branch,title=title,tags=tags,
                 content=c,version=(old['version'] if old else 0)+int(changed),revision=(old['revision'] if old else 0)+1,
                 record_kind=old['record_kind'] if old else 'automatic' if automatic else 'template',
                 favorite=bool(data.get('favorite',old['favorite'] if old else False)),
                 deleted_at=old.get('deleted_at') if old else None,created_at=old['created_at'] if old else now,updated_at=now,
                 source=copy.deepcopy(data.get('source',old.get('source',{}) if old else {})))
        if 'removed' in data: row['deleted_at']=(row['deleted_at'] or now) if data['removed'] else None
        if changed:
            version=dict(version=row['version'],schema_version=1,content=c,source=row['source'],created_at=now)
            db.execute('INSERT INTO versions VALUES(?,?,?)',(row['id'],row['version'],encode(version)))
        db.execute('INSERT INTO entries VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(row['id'],source_key,encode(row)))
        return row

    def save(self, data, ident=None):
        with self.connect(True) as db:
            key=data.get('request_id')
            if not ident and key:
                existing=db.execute('SELECT body FROM receipts WHERE id=?',('manual:'+str(key),)).fetchone()
                if existing: return self._get(db,'entries',json.loads(existing[0])['id'])
            row=self._save(db,data,ident)
            if not ident and key: db.execute('INSERT INTO receipts VALUES(?,?)',('manual:'+str(key),encode(dict(id=row['id']))))
            return row

    def collect(self, receipt, items):
        with self.connect(True) as db:
            found=db.execute('SELECT body FROM receipts WHERE id=?',(receipt,)).fetchone()
            if found: return json.loads(found[0])
            ids=[]
            for data in items:
                key=data['source_key']
                found=db.execute('SELECT id,body FROM entries WHERE source_key=?',(key,)).fetchone()
                if found:
                    old=json.loads(found[1])
                    if old.get('source',{}).get('saved_at',0)>data.get('source',{}).get('saved_at',0):
                        ids.append(old['id']);continue
                    # Organization and user labels survive all subsequent project saves.
                    data={**data,**{k:old[k] for k in ('purpose','branch','title','tags','favorite')}}
                row=self._save(db,data,found[0] if found else None,key,automatic=True)
                ids.append(row['id'])
            result=dict(state='collected',entries=ids)
            db.execute('INSERT INTO receipts VALUES(?,?)',(receipt,encode(result)))
            return result

    def backup(self, target):
        with self.connect() as source:
            dest=sqlite3.connect(target)
            try: source.backup(dest)
            finally: dest.close()

    def favorite_current(self, data):
        """Favorite only an unchanged committed authoring record, without saving a project."""
        c=content(data.get('content'));origin=data.get('origin') or {}
        with self.connect(True) as db:
            for raw in db.execute('SELECT body FROM entries'):
                row=json.loads(raw[0]);source=row.get('source',{})
                if row['record_kind']!='automatic' or row.get('deleted_at') or row['content']!=c: continue
                if any(source.get(k)!=origin.get(k) for k in ('project','target','scope','model')): continue
                if row.get('branch') and self._get(db,'branches',row['branch']).get('deleted_at'): continue
                return self._save(db,dict(favorite=True,revision=row['revision']),row['id'])
        return None
