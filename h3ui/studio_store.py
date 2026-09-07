"""Versioned SQLite state; immutable artifacts are addressed by UUID/hash."""
import json, sqlite3, threading, time, uuid
from contextlib import contextmanager
from pathlib import Path

class Conflict(ValueError):pass

class StudioStore:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.db=self.root/'studio.sqlite3'
        with self.connect() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, revision INTEGER, body TEXT);
            CREATE TABLE IF NOT EXISTS changes(token TEXT PRIMARY KEY, project TEXT, revision INTEGER, body TEXT, expires REAL, applied INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, project TEXT, body TEXT);
            CREATE TABLE IF NOT EXISTS defaults(mode TEXT PRIMARY KEY, body TEXT);''')
    @contextmanager
    def connect(self):
        connection=sqlite3.connect(self.db,timeout=30)
        try:
            with connection:yield connection
        finally:connection.close()
    def directory(self,pid):
        if not pid or any(c not in '0123456789abcdef-' for c in pid):raise ValueError('项目ID不合法')
        return self.root/pid
    def create(self,body):
        p={**body,'id':str(uuid.uuid4()),'revision':1,'schema_version':5,'created_at':time.time(),'updated_at':time.time()}
        with self.lock,self.connect() as c:c.execute('INSERT INTO projects VALUES(?,?,?)',(p['id'],1,json.dumps(p,ensure_ascii=False)))
        self.directory(p['id']).mkdir(exist_ok=True)
        return p
    def get(self,pid,include_deleted=False):
        with self.connect() as c:r=c.execute('SELECT body FROM projects WHERE id=?',(pid,)).fetchone()
        if not r:raise KeyError('项目不存在')
        p=json.loads(r[0])
        if p.get('deleted_at') and not include_deleted:raise KeyError('项目已删除，可在项目档案的已删除列表中恢复')
        return p
    def list(self,trash=False):
        with self.connect() as c:rows=c.execute('SELECT body FROM projects').fetchall()
        return sorted([p for r in rows if bool((p:=json.loads(r[0])).get('deleted_at'))==trash],key=lambda x:x['updated_at'],reverse=True)
    def trash(self,pid,revision,restore=False):
        with self.lock:
            p=self.get(pid,include_deleted=True)
            if p['revision']!=revision:raise Conflict('项目已更新，请刷新档案后重试')
            if p['status'] in ['generating','assembling','preparing']:raise Conflict('该项目仍在制作或准备中，请完成或停止任务后再删除')
            if restore:p.pop('deleted_at',None)
            else:p['deleted_at']=time.time()
            return self.save(p,revision)
    def save(self,p,expected):
        with self.lock,self.connect() as c:
            p={**p,'revision':expected+1,'updated_at':time.time()}
            result=c.execute('UPDATE projects SET revision=?,body=? WHERE id=? AND revision=?',(p['revision'],json.dumps(p,ensure_ascii=False),p['id'],expected))
            if result.rowcount!=1:raise Conflict('项目已更新，请刷新后重新保存')
        return p
    def mutate(self,pid,fn):
        with self.lock:
            p=self.get(pid);v=p['revision'];fn(p);return self.save(p,v)
    def asset(self,pid,aid):
        with self.connect() as c:r=c.execute('SELECT body FROM assets WHERE id=? AND project=?',(aid,pid)).fetchone()
        if not r:raise ValueError('素材不存在或不属于本项目')
        return json.loads(r[0])
    def assets(self,pid):
        with self.connect() as c:rows=c.execute('SELECT body FROM assets WHERE project=?',(pid,)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def add_asset(self,pid,a):
        with self.connect() as c:c.execute('INSERT INTO assets VALUES(?,?,?)',(a['id'],pid,json.dumps(a,ensure_ascii=False)))
    def stage(self,pid,rev,data):
        token=uuid.uuid4().hex
        with self.connect() as c:c.execute('INSERT INTO changes VALUES(?,?,?,?,?,0)',(token,pid,rev,json.dumps(data,ensure_ascii=False),time.time()+1800))
        return token
    def apply(self,pid,token):
        with self.lock,self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT revision,body,expires,applied FROM changes WHERE token=? AND project=?',(token,pid)).fetchone()
            if not row or row[2]<time.time() or row[3]:raise Conflict('确认方案已失效，请重新预检')
            current=c.execute('SELECT revision,body FROM projects WHERE id=?',(pid,)).fetchone()
            if current[0]!=row[0]:raise Conflict('项目在确认期间发生变化，请重新预检')
            plan=json.loads(row[1]);p=plan['project'];p.update(revision=row[0]+1,updated_at=time.time())
            for a in plan.get('assets_to_add',[]):
                if a['project']!=pid:raise ValueError('导入素材项目归属不一致')
                if not Path(a['path']).is_file():raise ValueError('资产副本尚未准备完成，请从资产引用确认入口应用')
                body={k:v for k,v in a.items() if k!='_library_source'}
                c.execute('INSERT OR IGNORE INTO assets VALUES(?,?,?)',(a['id'],pid,json.dumps(body,ensure_ascii=False)))
            p.setdefault('changes',[]).append({'time':time.time(),'summary':plan['summary'],'revision':p['revision']})
            c.execute('UPDATE projects SET revision=?,body=? WHERE id=?',(p['revision'],json.dumps(p,ensure_ascii=False),pid))
            c.execute('UPDATE changes SET applied=1 WHERE token=?',(token,))
        return p
    def get_default(self,mode):
        with self.connect() as c:r=c.execute('SELECT body FROM defaults WHERE mode=?',(mode,)).fetchone()
        return json.loads(r[0]) if r else None
    def set_default(self,mode,settings):
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO defaults VALUES(?,?)',(mode,json.dumps(settings,ensure_ascii=False)))
