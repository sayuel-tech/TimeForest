"""Portable media packages: relative paths, checksums, explicit bindings and no execution."""
import copy
import json
import re
import shutil
import time
import zipfile
from pathlib import Path, PurePosixPath

from .media import digest, inspect
from .store import encode, uid


def redact(value):
    if isinstance(value,dict):
        return {k:redact(v) for k,v in value.items() if not re.search(r'password|secret|api.?key|authorization|cookie|credential|access.?token',k,re.I)}
    if isinstance(value,list):return [redact(x) for x in value]
    if isinstance(value,str):
        value=re.sub(r'(?i)Bearer\s+\S+','[credential omitted]',value)
        value=re.sub(r'\bsk-[A-Za-z0-9_-]{12,}','[credential omitted]',value)
        if re.match(r'^(?:[A-Za-z]:[/\\]|[/\\]{2}|/(?:home|Users|mnt|tmp|var)/)',value):
            return Path(value.replace('\\','/')).name
        value=re.sub(r'(?i)https?://[^\s/]+:[^\s@]+@','[connection omitted] ',value)
    return value


class Packs:
    def __init__(self,library):self.lib=library

    def preview(self,data):
        snapshots={};excluded=[]
        def collect(aid,version=None):
            item=self.lib.store.get(aid,version);snap=item['snapshot'];key=snap['id']
            if key in snapshots:return
            if len(snapshots)>=128:raise ValueError('单个素材包最多128项版本，请分批导出')
            snapshots[key]=copy.deepcopy(snap)
            for binding in snap.get('bindings',[]):
                if data.get('bindings') and binding.get('default',True):collect(binding['asset'],binding['version'])
                else:excluded.append(dict(asset=binding['asset'],version=binding['version']))
        if not data.get('assets') or len(data['assets'])>100:raise ValueError('请选择1～100项资产')
        for selected in data['assets']:collect(selected['asset'],selected.get('version'))
        files={}
        for snap in snapshots.values():
            snap['bindings']=[x for x in snap.get('bindings',[]) if x['version'] in snapshots]
            for m in snap['media']:
                obj=self.lib.store.object(m['hash'])
                files[obj['hash']]=dict(hash=obj['hash'],path='media/'+obj['hash']+obj['extension'],bytes=obj['bytes'])
            if snap.get('cover_hash'):
                obj=self.lib.store.object(snap['cover_hash'])
                files[obj['hash']]=dict(hash=obj['hash'],path='media/'+obj['hash']+obj['extension'],bytes=obj['bytes'])
            if not data.get('documents',True):
                snap['record_prompt']='';snap['description']=''
            if not data.get('workflows',False):
                snap['provenance']={k:v for k,v in snap.get('provenance',{}).items() if k in ('type','project_name','candidate','seed','composite','operation')}
                for m in snap['media']:m.pop('provenance',None)
        category_ids={c for snap in snapshots.values() for c in snap.get('categories',[])}
        manifest=redact(dict(format='time-forest-assets',version=1,created=time.time(),assets=list(snapshots.values()),files=list(files.values()),
                             categories=[c for c in self.lib.store.catalog()['categories'] if c['id'] in category_ids]))
        token=uid()
        with self.lib.store.connect() as db:
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?)',(token,'pack_plan','ready',encode(manifest),time.time()))
        return dict(token=token,assets=[dict(id=x['asset_id'],name=x['name'],version=x['id']) for x in manifest['assets']],
                    files=len(files),bytes=sum(x['bytes'] for x in files.values()),excluded_bindings=excluded,
                    note='仅含列出的媒体与勾选资料；采用相对路径并移除已识别的凭据字段和绝对路径。工作流附件不会执行。')

    def export(self,data,progress):
        with self.lib.store.connect() as db:
            row=db.execute("SELECT body FROM operations WHERE key=? AND type='pack_plan'",(data['token'],)).fetchone()
        if not row:raise ValueError('素材包预览已失效')
        manifest=json.loads(row[0]);directory=self.lib.root/'exports';directory.mkdir(exist_ok=True)
        output=directory/(data['token']+'.zip');temp=output.with_suffix('.tmp')
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
            archive.writestr('manifest.json',encode(manifest))
            for i,file in enumerate(manifest['files']):
                progress(i/max(1,len(manifest['files'])),'打包原媒体')
                obj=self.lib.store.object(file['hash']);path=self.lib.store.path(obj['path'])
                if digest(path)!=file['hash']:raise ValueError('素材原件校验失败')
                archive.write(path,file['path'])
        temp.replace(output)
        return dict(download='/api/v5/library/packs/'+data['token'],name='时间森林素材包.zip',bytes=output.stat().st_size)

    def stage(self,stream):
        token=uid();path=self.lib.root/'staging'/(token+'.zip')
        size=0
        with path.open('xb') as out:
            for chunk in iter(lambda:stream.read(1024*1024),b''):
                size+=len(chunk)
                if size>self.lib.max_bytes:raise ValueError('素材包超过文件上限')
                out.write(chunk)
        preview=self.read_manifest(path)
        with self.lib.store.connect() as db:
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?)',(token,'pack_upload','ready',encode({'path':str(path),'hash':digest(path)}),time.time()))
        return dict(token=token,assets=[dict(name=x['name'],version=x['id']) for x in preview['assets']],
                    bytes=sum(x['bytes'] for x in preview['files']),note='将在本地创建独立资产身份和版本，核验文件哈希；不会安装模型、节点或运行工作流。')

    def read_manifest(self,path):
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist())>2000 or archive.getinfo('manifest.json').file_size>20*1024**2:raise ValueError('素材包条目或清单过大')
            if len({x.filename for x in archive.infolist()})!=len(archive.infolist()):raise ValueError('素材包包含重复文件路径')
            manifest=json.loads(archive.read('manifest.json'))
            if manifest.get('format')!='time-forest-assets' or manifest.get('version')!=1:raise ValueError('不支持的素材包格式')
            if not 1<=len(manifest.get('assets',[]))<=128:raise ValueError('素材包资产数量不支持')
            if sum(x.file_size for x in archive.infolist())>self.lib.max_bytes*2:raise ValueError('解包后大小超出限制')
            for file in manifest['files']:
                name=PurePosixPath(file['path'])
                if name.is_absolute() or '..' in name.parts or '\\' in file['path'] or ':' in file['path'] or name.parts[0]!='media':raise ValueError('素材包路径越界')
                info=archive.getinfo(file['path'])
                if info.file_size!=file['bytes'] or not re.fullmatch('[a-f0-9]{64}',file['hash']):raise ValueError('媒体大小或哈希声明不合法')
                if info.file_size>self.lib.max_bytes:raise ValueError('包内单文件超过上限')
            files={x['hash'] for x in manifest['files']};versions={x['id']:x for x in manifest['assets']}
            if len(versions)!=len(manifest['assets']):raise ValueError('资产包版本重复')
            seen=set();active=set()
            def visit(vid):
                if vid in active:raise ValueError('素材包存在循环绑定')
                if vid in seen:return
                if vid not in versions:raise ValueError('素材包缺失绑定依赖')
                active.add(vid)
                for b in versions[vid].get('bindings',[]):visit(b['version'])
                active.remove(vid);seen.add(vid)
            for snap in versions.values():
                if not snap.get('media') or any(m['hash'] not in files for m in snap['media']):raise ValueError('素材包缺失媒体依赖')
                if snap.get('cover_hash') and snap['cover_hash'] not in files:raise ValueError('素材包缺失封面依赖')
                visit(snap['id'])
            return manifest

    def import_pack(self,data,progress):
        with self.lib.store.connect() as db:
            row=db.execute("SELECT body FROM operations WHERE key=? AND type='pack_upload'",(data['token'],)).fetchone()
        if not row:raise ValueError('素材包上传不存在')
        registered=json.loads(row[0]);path=Path(registered['path'])
        if digest(path)!=registered['hash']:raise ValueError('素材包文件已变化')
        manifest=self.read_manifest(path);objects=[]
        with zipfile.ZipFile(path) as archive:
            for i,file in enumerate(manifest['files']):
                progress(.5*i/max(1,len(manifest['files'])),'校验并保存包内媒体')
                staged=self.lib.root/'staging'/(uid()+Path(file['path']).suffix)
                with archive.open(file['path']) as src,staged.open('xb') as out:shutil.copyfileobj(src,out,1024*1024)
                if digest(staged)!=file['hash']:raise ValueError('素材包媒体哈希不符')
                meta=inspect(staged);relative=f"objects/{file['hash'][:2]}/{file['hash']}{meta['extension']}"
                dest=self.lib.store.path(relative);dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists():staged.replace(dest)
                else:
                    if digest(dest)!=file['hash']:raise ValueError('库中同哈希原件损坏')
                    staged.unlink()
                objects.append(dict(hash=file['hash'],path=relative,bytes=file['bytes'],meta=meta))
        categories=self.lib.store.catalog()['categories'];known={x['id']:x['id'] for x in categories}
        for category in manifest.get('categories',[]):
            if category['id'] in known:continue
            match=next((x for x in self.lib.store.catalog()['categories'] if x['name']==category['name']),None)
            if not match:
                self.lib.store.category(category['name'])
                match=next(x for x in self.lib.store.catalog()['categories'] if x['name']==category['name'])
            known[category['id']]=match['id']
        versions={x['id']:x for x in manifest['assets']};imported={}
        def save(vid):
            if vid in imported:return imported[vid]
            snap=copy.deepcopy(versions[vid]);bindings=[]
            for binding in snap.get('bindings',[]):
                child=save(binding['version']);bindings.append({**binding,'asset':child['id'],'version':child['version']})
            snap['bindings']=bindings;snap['categories']=[known[x] for x in snap.get('categories',[]) if x in known]
            snap['provenance']={'type':'portable_pack','original_version':vid,'original_asset':snap.get('asset_id'),'records':snap.get('provenance',{})}
            result=self.lib.store.save(snap,objects=objects,key='pack-import:'+registered['hash']+':'+vid)
            self.lib.write_manifest(result);imported[vid]=result
            progress(.5+.5*len(imported)/len(versions),'恢复资产与固定版本绑定')
            return result
        for vid in versions:save(vid)
        from .media import preview
        for obj in objects:
            try:preview(self.lib.store.path(obj['path']),obj['meta'],self.lib.root/'previews'/obj['hash']/'cover.png')
            except Exception:pass
        return dict(assets=[dict(id=x['id'],name=x['name']) for x in imported.values()],count=len(imported))
