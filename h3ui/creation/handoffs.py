"""Explicit image-task handoff and reviewed fixed-version return."""
import copy
from .contracts import request_contract,digest
from .service import uid
from . import plans
from ..studio_store import Conflict


class Handoffs:
    def __init__(self,creation,image):self.c=creation;self.image=image

    def create(self,pid,data):
        request_contract('ImageHandoff',data)
        if not self.image:raise ValueError('请启用原图片资产创作功能后再补图')
        def change(p):
            target=data['target']
            if target['project_id']!=pid:raise ValueError('补图目标归属不一致')
            if self.c.layer_hash(p,target['layer'],target['target_ids'])!=data['source_content_hash']:raise Conflict('补图来源已修改')
            known={r['id'] for r in p.get('creation_references',[])}
            if set(data['reference_ids'])-known:raise ValueError('补图参考不属于当前剧本')
            # Handoff creates a normal image task. No generation or model call.
            references=[r for r in p.get('creation_references',[]) if r['id'] in data['reference_ids'] and r['kind']=='image']
            if len(references)!=len(data['reference_ids']) or len(references)>2:raise ValueError('补图任务可选择零至两张参考图片')
            image=self.image.create(p['name']+' · 剧本补图','dual' if len(references)==2 else 'single' if references else 'text')
            task=image['tasks'][0];task['prompt']=data['image_prompt_text']
            hid=uid();record=dict(handoff_id=hid,script_project_id=pid,target=copy.deepcopy(target),source_content_hash=data['source_content_hash'],reference_purpose=data['reference_purpose'],image_project_id=image['id'],image_task_id=task['id'],reference_ids=data['reference_ids'],return_context=data['return_context'])
            task['authoring_handoff']=record
            for key,reference in zip(('A','B'),references):
                fixed=reference['library_reference'];input=self.image.library_input(image['id'],dict(asset=fixed['asset'],version=fixed['version'],media=fixed['media']));task[key]=input['id']
            self.image.store.put('tasks',task)
            image_project=self.image.store.project(image['id']);image_project['authoring_handoff']=record;self.image.store.put('projects',image_project)
            p.setdefault('image_handoffs',[]).append(record)
            return [hid,image['id']],{}
        receipt=self.c.mutate(pid,data,change)
        return dict(receipt=receipt,handoff=next(h for h in self.c.get(pid)['image_handoffs'] if h['handoff_id']==receipt['changed_ids'][0]))

    def preview(self,pid,data):
        request_contract('ImageBindPreflight',data);p=self.c.get(pid,'authoring')
        if p['revision']!=data['revision']:raise Conflict('剧本已修改')
        h=next((h for h in p.get('image_handoffs',[]) if h['handoff_id']==data['handoff_id']),None)
        if not h:raise ValueError('补图来源不存在')
        _,m,obj=self.c.references.fixed(data['asset_ref'],data['asset_version'])
        if obj['kind']!='image':raise ValueError('补图回填需要图片资产')
        target=h['target'];stale=self.c.layer_hash(p,target['layer'],target['target_ids'])!=h['source_content_hash']
        if stale and data['mode']=='replace_active':raise Conflict('原剧本目标已变化，只能先添加为备选再核对')
        change=dict(change_id=uid(),label='添加为视觉备选' if data['mode']=='append_alternative' else '替换当前用途的视觉参考',source_changed=stale)
        return plans.make(self.c.store,p,'image_bind',[change],dict(request=data,handoff=h,media=m))

    def apply(self,pid,data):
        request_contract('ApplyPlan',data)
        def change(p):
            plan=plans.read(self.c.store,p,data,'image_bind')
            if data['selected_change_ids']!=[plan['changes'][0]['change_id']]:raise ValueError('请选择需要应用的补图变化')
            v=plan['payload'];request=v['request'];h=v['handoff'];self.c.references.fixed(request['asset_ref'],request['asset_version'],v['media']['id'])
            row=self.c.layer(p,'visual_references');content=copy.deepcopy(row['content'] if row else dict(references=[]));targets=h['target']['target_ids'] or [pid]
            if request['mode']=='replace_active':
                for r in content['references']:
                    if r['scope_target_id'] in targets and r['purpose']==h['reference_purpose']:r['active']=False
            for target in targets:
                content['references'].append(dict(id='tmp:'+uid(),scope_target_id=target,purpose=h['reference_purpose'],asset_ref=request['asset_ref'],asset_version=request['asset_version'],intent_text='',control_data_artifact_id=None,active=request['mode']=='replace_active'))
            asset,medium,obj=self.c.references.fixed(request['asset_ref'],request['asset_version'],v['media']['id'])
            fixed=dict(asset=asset['id'],version=asset['snapshot']['id'],media=medium['id'],hash=medium['hash']);rid=digest(fixed)[:32]
            refs=p.setdefault('creation_references',[])
            if not any(r['id']==rid for r in refs):refs.append(dict(id=rid,library_reference=fixed,name=asset['name'],kind='image',purpose='scene',subject='',url='/api/v5/library/media/'+medium['hash']))
            return self.c.write_layer(p,dict(layer='visual_references',target_ids=[],base_content_hash=row['content_hash'] if row else None,content=content,update_mode='replace_scope',removed_target_ids=[]))
        receipt=self.c.mutate(pid,data,change);self.c.references.usage(pid,data['request_key']);return receipt
