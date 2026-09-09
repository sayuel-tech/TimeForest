"""Fixed library references for writing; only explicit imports mutate a project."""
import copy
import base64
import io
from PIL import Image, ImageOps
from .contracts import digest, validate


class References:
    def __init__(self,creation):self.c=creation;self.lib=creation.library

    def fixed(self,asset,version,media=None):
        item=self.lib.store.get(asset,version)
        if item.get('deleted'):raise ValueError('资产已移除，请先恢复')
        entries=item['snapshot']['media']
        entry=next((m for m in entries if m['id']==media),None) if media else next((m for m in entries if m.get('role')=='primary'),entries[0] if entries else None)
        if not entry:raise ValueError('所选固定版本没有对应媒体')
        obj=self.lib.store.object(entry['hash'])
        return item,entry,obj

    def attach(self,pid,data):
        validate(data,{'type':'object','required':['revision','request_key','asset','version','media','purpose','subject'],
          'properties':{'revision':{'type':'integer'},'request_key':{'type':'string','minLength':1},
            **{k:{'type':'string','minLength':1} for k in ['asset','version','media','purpose']},'subject':{'type':'string'},'binding_need_ref':{'type':'string'}},'additionalProperties':False})
        def change(p):
            self.c.get(pid,'authoring')
            if data.get('binding_need_ref') and data['binding_need_ref'] not in {n['ref'] for n in (self.c.layer(p,'asset_bindings') or {}).get('content',{}).get('needs',[])}:raise ValueError('绑定的需求不存在')
            item,m,obj=self.fixed(data['asset'],data['version'],data['media'])
            if obj['kind'] not in ('image','audio'):raise ValueError('剧本参考接收图片或声音')
            purpose=data['purpose'];subject=data['subject']
            choices=['voice'] if obj['kind']=='audio' else ['character','face','costume','scene','palette','prop']
            if purpose not in choices:raise ValueError('素材用途与类型不符')
            if purpose in ('character','face','costume','voice') and (not subject.isascii() or not subject.isdigit() or not 1<=int(subject)<=99):raise ValueError('角色编号须为1～99')
            reference=dict(asset=item['id'],version=item['snapshot']['id'],media=m['id'],hash=m['hash'])
            rid=digest([reference,data['binding_need_ref']])[:32] if data.get('binding_need_ref') else digest(reference)[:32]
            values=p.setdefault('creation_references',[])
            existing=next((r for r in values if r['id']==rid),None)
            row=dict(id=rid,library_reference=reference,name=item['name'],kind=obj['kind'],purpose=purpose,subject=subject,
                     url='/api/v5/library/media/'+m['hash'])
            if existing:existing.update(row)
            else:values.append(row)
            return [rid],{}
        result=self.c.mutate(pid,data,change)
        self.usage(pid,data['request_key'])
        return result

    def usage(self,pid,key):
        rows=self.c.get(pid).get('creation_references',[])
        return self.lib.complete_usage(pid,[dict(id=r['id'],reference=r['library_reference']) for r in rows],key)

    def remove(self,pid,data):
        validate(data,{'type':'object','properties':{'revision':{'type':'integer'},'request_key':{'type':'string','minLength':1},'reference_id':{'type':'string','minLength':1}},'required':['revision','request_key','reference_id'],'additionalProperties':False})
        def change(p):
            refs=p.get('creation_references',[]);ref=next((r for r in refs if r['id']==data['reference_id']),None)
            if not ref:raise ValueError('参考素材已不在当前剧本')
            fixed=ref['library_reference']
            bindings=(self.c.layer(p,'asset_bindings') or {}).get('content',{}).get('bindings',[])
            visual=(self.c.layer(p,'visual_references') or {}).get('content',{}).get('references',[])
            if any(b.get('asset_ref')==fixed['asset'] and b.get('asset_version')==fixed['version'] and (b.get('state')=='bound' or b.get('active')) for b in bindings+visual):raise ValueError('此素材仍用于资产绑定或当前视觉参考。请先在对应范围停用或换选，再移除素材引用。')
            p['creation_references']=[r for r in refs if r['id']!=ref['id']];return [ref['id']],{}
        result=self.c.mutate(pid,data,change);self.usage(pid,data['request_key']);return result

    def materials(self,p):
        result=[]
        for row in p.get('creation_references',[]):
            ref=row['library_reference']
            result.append(dict(reference_key=row['id'],kind='image' if row['kind']=='image' else 'text',
                content=row['name']+' · '+row['purpose']+' '+row.get('subject',''),
                media=dict(media_id=ref['media'],version=ref['version'],content_hash=ref['hash']) if row['kind']=='image' else None))
        return result

    def image_parts(self,p,materials):
        parts=[]
        for material in materials:
            if material['kind']!='image':continue
            row=next((r for r in p.get('creation_references',[]) if r['id']==material['reference_key']),None)
            if not row:raise ValueError('图片不属于本次剧本')
            ref=row['library_reference'];_,_,obj=self.fixed(ref['asset'],ref['version'],ref['media'])
            if ref['hash']!=material['media']['content_hash']:raise ValueError('图片版本已变化')
            path=self.lib.store.path(obj['path'])
            from ..studio_media import digest as file_digest
            if file_digest(path)!=ref['hash']:raise ValueError('图片原件缺失或已变化')
            with Image.open(path) as image:
                image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1536,1536))
                buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=90)
            parts.extend([dict(type='text',text='图片参考 '+material['reference_key']),dict(type='image_url',image_url=dict(url='data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()))])
        return parts
