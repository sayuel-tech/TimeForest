"""Short-lived review plans use the existing StudioStore changes table."""
import json
import time
from .contracts import digest
from ..studio_store import Conflict


def make(store,p,kind,changes,payload):
    value=dict(kind=kind,changes=changes,payload=payload)
    token=store.stage(p['id'],p['revision'],value)
    return dict(plan_id=token,plan_hash=digest(value),project_id=p['id'],revision=p['revision'],changes=changes)


def read(store,p,data,kind):
    with store.connect() as db:
        row=db.execute('SELECT revision,body,expires FROM changes WHERE token=? AND project=?',(data['plan_id'],p['id'])).fetchone()
    if not row or row[2]<time.time():raise Conflict('确认内容已过期，请重新查看变化')
    value=json.loads(row[1])
    if row[0]!=p['revision'] or value['kind']!=kind or digest(value)!=data['plan_hash']:raise Conflict('确认期间内容已变化，请重新查看')
    return value
