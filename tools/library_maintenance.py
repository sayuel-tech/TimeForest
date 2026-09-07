"""Offline library maintenance. Dry-run by default; originals are never deleted by migration."""
import argparse
import json
import os
import re
import shutil
import socket
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from h3ui.asset_library.service import Library
from h3ui.asset_library.media import digest
from h3ui.config import ROOT


def offline(config):
    host=config.get('host','127.0.0.1');port=int(config.get('port',5093))
    if host in ('0.0.0.0','::'):host='127.0.0.1'
    try:
        with socket.create_connection((host,port),timeout=.5):pass
    except OSError:return
    raise ValueError('请先停止本站服务再维护目录。生成引擎无需启动，也不会由工具操作。')


def save_config(path,config):
    old=path.with_name(path.name+'.before-library-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
    if old.exists():raise ValueError('同名配置备份存在，请稍后再操作')
    shutil.copy2(path,old)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,path)
    return str(old)


def root_path(value):
    p=Path(value).expanduser()
    return (p if p.is_absolute() else ROOT/p).resolve()


def cleanup_plan(lib,days=7):
    cutoff=time.time()-max(7,int(days))*86400;items=[]
    with lib.store.connect() as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='local_tasks'").fetchone()
        rows=db.execute("SELECT payload,action FROM local_tasks WHERE state='done' AND updated<?",(cutoff,)).fetchall() if exists else []
    for row in rows:
        data=json.loads(row['payload']);token=data.get('operation_id') if row['action']=='derive' else None
        if not token or not re.fullmatch('[a-f0-9]{32}',token):continue
        path=lib.store.path('staging/'+token)
        if not path.is_dir():continue
        files=list(path.rglob('*'))
        if any(path not in p.resolve().parents for p in files):raise ValueError('临时目录包含越界链接，停止清理')
        items.append(dict(path=str(path),bytes=sum(p.stat().st_size for p in files if p.is_file())))
    return dict(items=items,bytes=sum(x['bytes'] for x in items),note='仅清理至少7天前完成派生的临时副本。所有资产版本、回收站、绑定、原件、备份和未完成上传均保留。')


def maintain(config_path,action,target=None,apply=False,days=7):
    config_path=Path(config_path).resolve()
    config=json.loads(config_path.read_text(encoding='utf-8'));offline(config)
    source=root_path(config.get('asset_library_dir',ROOT.parent/'TimeForestAssets'))
    if not (source/'library.sqlite3').is_file():raise ValueError('配置中的资产库不存在，停止维护')
    lib=Library(source,config)
    if action=='cleanup':
        plan=cleanup_plan(lib,days)
        if apply:
            for item in plan['items']:
                path=Path(item['path']).resolve()
                if path.parent != source/'staging':raise ValueError('临时清理路径越界')
                shutil.rmtree(path)
        return {**plan,'applied':apply}
    dest=Path(target or '').resolve()
    if not target or dest==source or source in dest.parents or dest in source.parents or dest.exists():
        raise ValueError('目标须为尚不存在的独立目录，不能覆盖原目录或嵌套迁移')
    plan=dict(action=action,source=str(source),target=str(dest),bytes=lib.storage()['stored_bytes'],applied=False)
    if not apply:return plan
    for name in ('staging','exports','previews','manifests'):
        if (source/name).exists() and any(source not in p.resolve().parents for p in (source/name).rglob('*')):raise ValueError('源库含越界文件链接，停止迁移')
    result=lib.backup(dest)
    lib.verify_backup(dest)
    # Resume buffers and human-facing previews are copied only after the authoritative snapshot verifies.
    for name in ('staging','exports','previews','manifests'):
        if (source/name).exists():shutil.copytree(source/name,dest/name,dirs_exist_ok=True)
    def moved(value):
        if isinstance(value,dict):return {k:moved(v) for k,v in value.items()}
        if isinstance(value,list):return [moved(v) for v in value]
        if isinstance(value,str):
            for part in ('staging','exports'):
                prefix=str(source/part)
                if value.startswith(prefix+os.sep) or value.startswith(prefix+'/'):return str(dest/part)+value[len(prefix):]
        return value
    with closing(sqlite3.connect(dest/'library.sqlite3')) as db:
        with db:
            for row in db.execute('SELECT key,body FROM operations').fetchall():
                db.execute('UPDATE operations SET body=? WHERE key=?',(json.dumps(moved(json.loads(row[1])),ensure_ascii=False),row[0]))
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='local_tasks'").fetchone():
                for row in db.execute('SELECT id,payload FROM local_tasks').fetchall():
                    db.execute('UPDATE local_tasks SET payload=? WHERE id=?',(json.dumps(moved(json.loads(row[1])),ensure_ascii=False),row[0]))
    manifest=json.loads((dest/'backup.json').read_text(encoding='utf-8'))
    next(x for x in manifest['files'] if x['path']=='library.sqlite3')['hash']=digest(dest/'library.sqlite3')
    (dest/'backup.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
    lib.verify_backup(dest)
    config['asset_library_dir']=str(dest)
    previous=save_config(config_path,config)
    return {**plan,'applied':True,'previous_config':previous,'note':'原库完整保留；下次启动使用已校验的新目录。'}


def restore(config_path,backup,target,apply=False):
    path=Path(config_path).resolve();config=json.loads(path.read_text(encoding='utf-8'));offline(config)
    source=Path(backup).resolve();dest=Path(target).resolve()
    if dest.exists() or dest==source or source in dest.parents:raise ValueError('恢复目标必须是尚不存在的独立目录')
    verifier=object.__new__(Library);verifier.verify_backup(source)
    report=dict(backup=str(source),target=str(dest),applied=apply)
    if not apply:return report
    manifest=verifier.verify_backup(source)
    dest.mkdir(parents=True)
    for entry in manifest['files']:
        output=dest/entry['path'];output.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/entry['path'],output)
    shutil.copy2(source/'backup.json',dest/'backup.json');verifier.verify_backup(dest)
    with closing(sqlite3.connect(dest/'library.sqlite3')) as db:
        with db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='local_tasks'").fetchone():
                db.execute("UPDATE local_tasks SET state='failed',note='已从备份恢复原件；备份不含在途上传，请重新导入' WHERE state IN ('queued','running','interrupted')")
    config['asset_library_dir']=str(dest);report['previous_config']=save_config(path,config)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['migrate','restore','cleanup']);p.add_argument('--config',required=True)
    p.add_argument('--target');p.add_argument('--backup');p.add_argument('--apply',action='store_true');p.add_argument('--days',type=int,default=7)
    a=p.parse_args()
    try:
        result=restore(a.config,a.backup,a.target,a.apply) if a.action=='restore' else maintain(a.config,a.action,a.target,a.apply,a.days)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as exc:p.exit(1,str(exc)+'\n')
