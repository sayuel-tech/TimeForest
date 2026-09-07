"""Fixed project-owned reference media; draft bindings never rewrite run inputs."""
import copy
from pathlib import Path
from werkzeug.datastructures import FileStorage
from ..studio_inputs import inventory, public_inventory, validate
from . import media

PURPOSES = {'character','face','costume','scene','palette','prop','voice'}


class References:
    def reference_bindings(self, p, values):
        if not isinstance(values,list) or len(values)>12:
            raise ValueError('参考素材最多12项')
        rows=[];seen=set()
        for value in values:
            aid=value['id']
            if aid in seen: raise ValueError('同一参考素材不能重复绑定')
            seen.add(aid)
            a=next((a for a in p['assembly'].get('references',[]) if a['id']==aid),None)
            if not a: raise ValueError('参考素材不属于当前项目')
            purpose=value.get('purpose',a['purpose']);subject=str(value.get('subject',a.get('subject','')))
            if purpose not in PURPOSES or (a['kind']=='audio' and purpose!='voice') or (a['kind']=='image' and purpose=='voice'):
                raise ValueError('素材用途与类型不匹配')
            if purpose in ('character','face','costume','voice') and (not subject.isascii() or not subject.isdigit() or not 1<=int(subject)<=99):
                raise ValueError('角色ID须为1～99')
            rows.append(dict(id=aid,purpose=purpose,subject=subject))
        return rows

    def reference_assets(self,p,e,verify=True):
        rows=self.reference_bindings(p,e.get('references',[]));assets=[]
        for row in rows:
            a=copy.deepcopy(next(a for a in p['assembly'].get('references',[]) if a['id']==row['id']))
            a.update(row)
            if verify:self.path(p['id'],a['path'])
            if verify and media.digest(a['path'])!=a['sha256']: raise ValueError('参考素材文件已变化，请重新导入')
            assets.append(a)
        projection=dict(mode='image_story',settings=e['configurations'][e['recipe']])
        validate(projection,{},assets)
        return assets

    def import_reference(self,pid,data,upload=None):
        with self.lock:
            p=self.checked(pid,int(data['revision']));_,e=self.find_extension(p,data['extension'])
            reference=data.get('reference');purpose=data.get('purpose');subject=data.get('subject','1')
            if reference:
                item=self.lib.store.get(reference['asset'],reference['version'])
                if item.get('deleted'): raise ValueError('请先恢复资产')
                m=next((m for m in item['snapshot']['media'] if m['id']==reference['media']),None)
                if not m: raise ValueError('素材不属于所选固定版本')
                obj=self.lib.store.object(m['hash']);kind=obj['kind']
                if kind not in ('image','audio'): raise ValueError('续接参考仅接收图片和声音')
                path=self.lib.store.path(obj['path'])
                purpose=purpose or ('voice' if kind=='audio' else 'character')
                with Path(path).open('rb') as stream:
                    a=self.st.jobs.run_inline('assembly_reference',pid,lambda:self.st.upload(pid,FileStorage(stream=stream,filename='reference'+obj['extension']),kind,purpose,subject))
                a['name']=item['name'];a['library_reference']=dict(asset=item['id'],version=item['snapshot']['id'],media=m['id'],hash=m['hash'])
            else:
                kind=data.get('kind')
                if kind not in ('image','audio') or upload is None: raise ValueError('请选择图片或参考声音')
                purpose=purpose or ('voice' if kind=='audio' else 'character')
                a=self.st.jobs.run_inline('assembly_reference',pid,lambda:self.st.upload(pid,upload,kind,purpose,subject))
            p['assembly'].setdefault('references',[]).append(a)
            e['references']=self.reference_bindings(p,e.get('references',[])+[dict(id=a['id'],purpose=purpose,subject=subject)])
            self.reference_assets(p,e)
            p['assembly']['draft_revision']=p['assembly'].get('draft_revision',1)+1
            self.store.save(p,p['revision'])
            return self.snapshot(pid)

    def reference_snapshot(self,p):
        for c in p['assembly']['clips']:
            for e in c['extensions']:
                assets=self.reference_assets(p,e,verify=False)
                e['input_inventory']=public_inventory(inventory(dict(mode='image_story'),{},assets))
        p['assembly']['references']=[self.st.public_asset(a) for a in p['assembly'].get('references',[])]
