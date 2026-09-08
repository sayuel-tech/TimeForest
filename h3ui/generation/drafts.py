"""A separate authoring buffer; never mutates an in-flight project/run snapshot."""
import copy
import json
import time

from ..studio_store import Conflict

PROJECT_FIELDS=('name','duration','review','settings','storyboard_version','timing_mode','source_options','swap_prompt','prompt_sources')
SEGMENT_FIELDS=('id','index','prompt','prompt_mode','staging','beats','voice','soundscape','music','ending','assets','inherit_ids',
                'asset_mode','seed_mode','seed','boundary','swap_prompt_mode','swap_custom_prompt','prompt_sources','speaker_order')


class DraftStore:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS authoring_drafts(project TEXT PRIMARY KEY, revision INTEGER, base_revision INTEGER, body TEXT, updated REAL)')

    def get(self,pid):
        with self.store.connect() as db:row=db.execute('SELECT revision,base_revision,body,updated FROM authoring_drafts WHERE project=?',(pid,)).fetchone()
        return dict(revision=row[0],base_revision=row[1],body=json.loads(row[2]),updated=row[3]) if row else None

    def save(self,pid,data):
        project=self.store.get(pid)
        incoming=data.get('body',{})
        body={k:copy.deepcopy(incoming[k]) for k in PROJECT_FIELDS if k in incoming}
        body['segments']=[{k:copy.deepcopy(s[k]) for k in SEGMENT_FIELDS if k in s} for s in incoming.get('segments',[])][:3000]
        text=json.dumps(body,ensure_ascii=False)
        if len(text)>10*1024*1024:raise ValueError('草稿过大，请减少素材与正文数量')
        with self.store.lock,self.store.connect() as db:
            row=db.execute('SELECT revision FROM authoring_drafts WHERE project=?',(pid,)).fetchone()
            revision=row[0] if row else 0
            if int(data.get('revision',0))!=revision:raise Conflict('另一个页面已保存草稿，请先载入或另存当前文本')
            db.execute('INSERT OR REPLACE INTO authoring_drafts VALUES(?,?,?,?,?)',(pid,revision+1,project['revision'],text,time.time()))
        return self.get(pid)

    def discard(self,pid,revision):
        with self.store.connect() as db:
            if db.execute('DELETE FROM authoring_drafts WHERE project=? AND revision=?',(pid,revision)).rowcount!=1:raise Conflict('草稿已更新，请重新核对后移除')
