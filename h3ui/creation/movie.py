"""Movie organization: frozen script bundles, independent takes and edit decisions."""
import copy
import time
from .contracts import digest,read,validate,request_contract
from .service import uid
from . import plans
from ..studio_store import Conflict
from ..studio_recipes import defaults

PROFILE_RECIPES={f'movie.{kind}.{recipe}':dict(recipe=recipe,prompt_mode='full',context_kind='external_decoded_av' if kind=='tail' else 'independent')
                 for kind in ('independent','tail') for recipe in ('dance_split','official_image')}
PROFILE_RECIPES.update({k+'.structured':dict(v,prompt_mode='structured') for k,v in list(PROFILE_RECIPES.items())})


class Movie:
    def __init__(self,creation):
        self.c=creation;self.store=creation.store
        from .movie_execution import Execution
        self.execution=Execution(self)

    def checked(self,pid,data):
        p=self.c.get(pid,'movie')
        if p['revision']!=data['revision']:raise Conflict('电影项目已更新，请核对当前草稿')
        return p

    def catalog(self):
        result=self.c.st.recipes.catalog()
        result['recipes']=[r for r in result['recipes'] if r['id'] in ('dance_split','official_image')]
        result['parameters']=[f for f in result['parameters'] if f['key']!='export_fps']
        for recipe in result['recipes']:recipe['parameters']=[f for f in recipe['parameters'] if f['key']!='export_fps']
        result['profiles']=[dict(profile_id=k,profile_revision='1',**v) for k,v in PROFILE_RECIPES.items()]
        result['creation_contract_version']=1
        return result

    def bundle(self,p,sid):
        return next((b for b in reversed(p['content']['source_bundles']) if b['segment_id']==sid),None)

    def frozen(self,p,sid):
        bundle=self.bundle(p,sid)
        if not bundle:raise ValueError('电影中没有这个剧本片段')
        return bundle,p['artifacts'][bundle['snapshot_artifact_id']]

    def resolve_bindings(self,source,segment):
        from .bindings import resolve
        return resolve(self.c,source,segment['ref'])

    def source(self,source,segment):
        sid=segment['ref'];prompt=self.c.layer(source,'prompt',[sid]);value=prompt['content'] if prompt else {}
        tail=segment.get('dependency',{}).get('kind')=='upstream_tail'
        shot=next(s for s in self.c.layer(source,'storyboard')['content']['shots'] if s['ref']==segment['shot_ref'])
        profile=value.get('profile_id') or 'movie.'+('tail' if tail else 'independent')+'.'+shot.get('workflow_recipe','dance_split')
        if profile not in PROFILE_RECIPES:raise ValueError('剧本片段选择的生成配置尚未适配')
        from .bindings import references as bound_references
        bindings=self.resolve_bindings(source,segment);references=bound_references(source,bindings)
        visual=[r for r in (self.c.layer(source,'visual_references') or {}).get('content',{}).get('references',[]) if r.get('active') and r['scope_target_id'] in (source['id'],segment['shot_ref'],sid)]
        for visual_ref in visual:
            _,medium,obj=self.c.references.fixed(visual_ref['asset_ref'],visual_ref['asset_version'])
            fixed=dict(asset=visual_ref['asset_ref'],version=visual_ref['asset_version'],media=medium['id'],hash=medium['hash'])
            if not any(r['library_reference']==fixed for r in references):
                references.append(dict(id=visual_ref['id'],library_reference=fixed,name='视觉参考 · '+visual_ref['purpose'],kind=obj['kind'],purpose='scene',subject='',visual_purpose=visual_ref['purpose']))
        contract=dict(input_contract_id=digest([source['id'],sid,profile,bindings,visual,references])[:32],revision='1',profile_id=profile,profile_revision='1',prompt_mode=PROFILE_RECIPES[profile]['prompt_mode'],slots=[])
        ordinals={'image':0,'audio':0}
        for ref in sorted(references,key=lambda r:0 if r['kind']=='image' else 1):
            fixed=ref['library_reference'];ordinals[ref['kind']]+=1
            contract['slots'].append(dict(slot_id=ref['id'],reference_key=ref['id'],media_kind=ref['kind'],purpose=ref['purpose'],application='engine_input',source=dict(kind='fixed_asset',media=dict(media_id=fixed['media'],version=fixed['version'],content_hash=fixed['hash'])),adapter_slot_key='ref_'+ref['kind']+'_'+str(ordinals[ref['kind']]-1),ordinal_label=('<Picture ' if ref['kind']=='image' else '<Audio ')+str(ordinals[ref['kind']])+'>'))
        if tail:contract['slots'].append(dict(slot_id='upstream',reference_key=segment['dependency']['upstream_ref'],media_kind='video',purpose='continuation',application='engine_input',source=dict(kind='future_upstream',upstream_segment_id=segment['dependency']['upstream_ref'],expected_end_state=segment.get('start_state',''),accepted_context_kind='external_decoded_av'),adapter_slot_key='context',ordinal_label=None))
        validate(contract,read('数据契约/input-contract.schema.json'))
        confirmations=copy.deepcopy(source['content']['confirmations'])
        confirmed=any(c['layer']=='prompt' and c['target_id']==sid and c['review_state']=='current' and c['content_hash']==(prompt or {}).get('content_hash') for c in confirmations)
        artifact=dict(segment=copy.deepcopy(segment),shot=copy.deepcopy(next(s for s in self.c.layer(source,'storyboard')['content']['shots'] if s['ref']==segment['shot_ref'])),prompt=copy.deepcopy(value),bindings=bindings,visual_references=copy.deepcopy(visual),references=references,input_contract=contract,confirmations=confirmations,script_title=source['name'])
        aid=uid();bundle=dict(bundle_id=uid(),script_project_id=source['id'],shot_id=segment['shot_ref'],segment_id=sid,source_revision=source['revision'],segment_hash=digest(segment),prompt_hash=prompt['content_hash'] if prompt else None,prompt_mode=value.get('prompt_mode'),binding_hash=digest(bindings),input_contract_hash=digest(contract),profile_id=profile,profile_revision='1',ready_state='ready' if confirmed else 'draft',snapshot_artifact_id=aid)
        return bundle,artifact

    def authoring_preview(self,pid,sid,check=True):
        from ..studio_plan import aligned
        from ..studio_prompts import build
        from ..studio_inputs import inventory,validate_tags
        p=self.c.get(pid,'authoring');segment=next(s for s in self.c.layer(p,'segment')['content']['segments'] if s['ref']==sid)
        _,source=self.source(p,segment);profile=PROFILE_RECIPES[source['input_contract']['profile_id']]
        settings=self.c.st.recipes.normalize(dict(recipe=profile['recipe']),'image_story')
        head=22 if profile['context_kind']=='external_decoded_av' else 0;deliver=round(float(segment.get('planned_seconds') or 0)*24);raw=max(124,aligned(deliver+head))
        plan=dict(raw=raw,head=head,deliver=deliver,tail=max(0,raw-head-deliver));payload=source['prompt'].get('payload',{})
        projection=dict(id=pid,mode='image_story',settings=settings)
        text=payload.get('prompt_text','') if profile['prompt_mode']=='full' else build(projection,dict(payload.get('fields',{}),**plan,asset_mode='custom' if source['references'] else 'none'),source['references'])
        if check:validate_tags(text,inventory(projection,{},source['references']))
        return dict(actual_prompt_text=text,input_contract=source['input_contract'],frame_plan=plan,inference_executed=False,notice='起始/结束/构图等视觉图在当前 H3 配置中作为参考图片输入；不宣称强制首尾帧控制。电影参数变化后仍须重新检查。')

    def import_source(self,p,source,ids):
        segments=(self.c.layer(source,'segment') or {}).get('content',{}).get('segments',[])
        known={s['ref'] for s in segments}
        if set(ids)-known:raise ValueError('选择的剧本片段不存在')
        selected=[s for s in segments if not ids or s['ref'] in ids]
        # Match the script directory: shots first, stable segment order within each shot.
        shots=(self.c.layer(source,'storyboard') or {}).get('content',{}).get('shots',[])
        positions={shot['ref']:index for index,shot in enumerate(shots)}
        selected.sort(key=lambda segment:positions.get(segment['shot_ref'],len(positions)))
        for segment in selected:
            bundle,artifact=self.source(source,segment)
            p['content']['source_bundles'].append(bundle);p['artifacts'][bundle['snapshot_artifact_id']]=artifact
            if segment['ref'] not in p['content']['segment_order']:p['content']['segment_order'].append(segment['ref'])
        return [s['ref'] for s in selected]

    def sync_preview(self,pid,data):
        request_contract('SyncPreview',data);p=self.checked(pid,data);source=self.c.get(data['source_project_id'],'authoring')
        if source['id']!=p['content']['source_project_id'] or source['revision']!=data['source_revision']:raise Conflict('来源剧本或版本不一致')
        staged=copy.deepcopy(p);ids=self.import_source(staged,source,data['target_segment_ids'])
        changes=[dict(change_id=sid,label='同步片段及整套来源',segment_id=sid) for sid in ids]
        return plans.make(self.store,p,'script_sync',changes,dict(source_project_id=source['id'],source_revision=source['revision'],bundles=staged['content']['source_bundles'][len(p['content']['source_bundles']):],artifacts={b['snapshot_artifact_id']:staged['artifacts'][b['snapshot_artifact_id']] for b in staged['content']['source_bundles'][len(p['content']['source_bundles']):]}))

    def sync_apply(self,pid,data):
        request_contract('ApplyPlan',data)
        def change(p):
            plan=plans.read(self.store,p,data,'script_sync');payload=plan['payload']
            if self.c.get(payload['source_project_id'])['revision']!=payload['source_revision']:raise Conflict('来源剧本已更新，请重新比较')
            selected=set(data['selected_change_ids']);known={c['change_id'] for c in plan['changes']}
            if not selected or selected-known:raise ValueError('请选择有效的同步片段')
            for b in payload['bundles']:
                if b['segment_id'] not in selected:continue
                p['content']['source_bundles'].append(b);p['artifacts'][b['snapshot_artifact_id']]=payload['artifacts'][b['snapshot_artifact_id']]
                if b['segment_id'] not in p['content']['segment_order']:p['content']['segment_order'].append(b['segment_id'])
            return list(selected),{}
        return self.c.mutate(pid,data,change)

    def draft(self,p,sid):
        b,a=self.frozen(p,sid)
        return next((d for d in p['content']['generation_drafts'] if d['segment_id']==sid),dict(segment_id=sid,profile_id=b['profile_id'],parameter_overrides={},input_contract_id=a['input_contract']['input_contract_id'],reference_ids=[r['id'] for r in a['references']],upstream_take_id=None,upstream_range=None))

    def save_draft(self,pid,data):
        request_contract('SaveGenerationDraft',data)
        def change(p):
            _,source=self.frozen(p,data['segment_id']);profile=PROFILE_RECIPES.get(data['profile_id'])
            if not profile:raise ValueError('工作流配置不存在')
            if data['input_contract_id']!=source['input_contract']['input_contract_id']:raise Conflict('输入合同已更新，请先核对剧本来源')
            if set(data['reference_ids'])-{r['id'] for r in source['references']}:raise ValueError('参考不属于当前来源包')
            self.c.st.recipes.normalize(dict(data['parameter_overrides'],recipe=profile['recipe']),'image_story')
            if data['upstream_take_id']:
                take=self.take(p,data['upstream_take_id']);dependency=source['segment'].get('dependency',{})
                if take['movie_segment_id']!=dependency.get('upstream_ref'):raise ValueError('所选上游不是剧本中记录的依赖片段')
                self.valid_range(take,data['upstream_range'])
            draft={k:v for k,v in data.items() if k not in ('revision','request_key')}
            p['content']['generation_drafts']=[d for d in p['content']['generation_drafts'] if d['segment_id']!=data['segment_id']]+[draft]
            return [data['segment_id']],{}
        return self.c.mutate(pid,data,change)

    def take(self,p,tid):
        take=next((t for t in p.get('movie_takes',[]) if t['take_id']==tid),None)
        if not take:raise ValueError('生成结果不属于此电影项目')
        return take

    @staticmethod
    def valid_range(take,value):
        if not value or not 0<=value['in_ms']<value['out_ms']<=take['duration_ms']:raise ValueError('使用区间须在此结果有效时长内')

    def adopt(self,pid,data):
        request_contract('AdoptTake',data)
        def change(p):
            take=self.take(p,data['take_id'])
            if take['movie_segment_id']!=data['segment_id'] or take['state']!='available':raise ValueError('结果不能用于当前片段')
            self.execution.path(p,take)
            values=p['content']['adoptions'];existing=next((a for a in values if a['segment_id']==data['segment_id']),None)
            if existing:
                if existing['take_id']==take['take_id']:return [take['take_id']],{}
                existing.update(take_id=take['take_id'],selection_revision=existing['selection_revision']+1)
            else:values.append(dict(segment_id=data['segment_id'],take_id=take['take_id'],selection_revision=1))
            for t in p.get('movie_takes',[]):
                if t['movie_segment_id']==data['segment_id']:t['currently_adopted']=t is take
            return [take['take_id']],{}
        return self.c.mutate(pid,data,change)

    def item(self,take):return dict(id=uid(),movie_segment_id=take['movie_segment_id'],take_id=take['take_id'],media=copy.deepcopy(take['media']),range=dict(in_ms=0,out_ms=take['duration_ms']),included=True)

    def initialize_edit(self,pid,data):
        request_contract('InitializeEdit',data)
        def change(p):
            edit=p['content']['edit']
            if edit['initialized_at']:raise Conflict('剪辑已建立；请使用更新处理保留当前排序和区间')
            selected={a['segment_id']:a['take_id'] for a in p['content']['adoptions']}
            items=[self.item(self.take(p,selected[sid])) for sid in p['content']['segment_order'] if selected.get(sid)]
            if not items:raise ValueError('请先在生成页选用至少一个结果')
            edit.update(initialized_at=str(time.time()),items=items,order=[i['id'] for i in items]);return edit['order'],{}
        return self.c.mutate(pid,data,change)

    def save_edit(self,pid,data):
        request_contract('SaveEdit',data)
        def change(p):
            edit=p['content']['edit']
            if not edit['initialized_at'] or digest(edit)!=data['edit_content_hash']:raise Conflict('剪辑已变化，请核对当前时间轴')
            if set(data['order'])!={i['id'] for i in edit['items']}:raise ValueError('排序必须包含全部剪辑项，排除请使用区间项开关')
            if len({c['item_id'] for c in data['item_changes']})!=len(data['item_changes']):raise ValueError('剪辑项重复')
            for changes in data['item_changes']:
                item=next((i for i in edit['items'] if i['id']==changes['item_id']),None)
                if not item:raise ValueError('剪辑项不存在')
                self.valid_range(self.take(p,item['take_id']),changes['range']);item.update(range=changes['range'],included=changes['included'])
            edit['order']=data['order'];return data['order'],{}
        return self.c.mutate(pid,data,change)

    def seams(self,p):
        edit=p['content']['edit'];included=[next(i for i in edit['items'] if i['id']==iid) for iid in edit['order'] if next(i for i in edit['items'] if i['id']==iid)['included']];warnings=[]
        for index,item in enumerate(included):
            take=self.take(p,item['take_id']);snapshot=p['artifacts'][take['snapshot_id']];upstream=snapshot.get('upstream_take_id')
            if not upstream:continue
            previous=included[index-1] if index else None
            source_range=next((i.get('range') for i in snapshot.get('inputs',[]) if i['reference_key']=='upstream'),None)
            same=previous and previous['take_id']==upstream and source_range and previous['range']['out_ms']==source_range['out_ms'] and item['range']['in_ms']==0
            if not same:warnings.append(dict(id=digest([item,previous,upstream,source_range])[:32],item_id=item['id'],upstream_take_id=upstream,previous_take_id=previous['take_id'] if previous else None,message=f'片段 {index+1} 的生成上游或裁切边界与当前接点不同。可以保留这次剪辑，但不代表连续性已经验证。'))
        return warnings

    def edit_updates(self,pid,data):
        request_contract('EditUpdatesPreview',data);p=self.checked(pid,data);edit=p['content']['edit'];changes=[]
        if not edit['initialized_at']:raise ValueError('请先建立剪辑时间轴')
        if data['edit_content_hash']!=digest(edit):raise Conflict('剪辑已变化，请重新核对更新')
        for a in p['content']['adoptions']:
            item=next((i for i in edit['items'] if i['movie_segment_id']==a['segment_id']),None)
            if item and item['take_id']==a['take_id']:continue
            if item and any(h['item_id']==item['id'] and h['offered_take_id']==a['take_id'] and h['offered_selection_revision']==a['selection_revision'] for h in edit['handled_updates']):continue
            changes.append(dict(change_id=uid(),label='已有片段有新选用结果' if item else '新选用片段',item_id=item['id'] if item else None,**a))
        return plans.make(self.store,p,'edit_updates',changes,{})

    def apply_updates(self,pid,data):
        request_contract('EditUpdatesApply',data)
        def change(p):
            plan=plans.read(self.store,p,data,'edit_updates');edit=p['content']['edit'];seen=set()
            for decision in data['decisions']:
                offered=next((o for o in plan['changes'] if o['change_id']==decision['change_id']),None)
                if not offered or offered['change_id'] in seen:raise ValueError('更新选择无效或重复')
                seen.add(offered['change_id']);take=self.take(p,offered['take_id']);action=decision['action']
                item=next((i for i in edit['items'] if i['id']==offered['item_id']),None)
                if item:
                    if action not in ('replace','keep','exclude'):raise ValueError('已有片段只能替换、保留或排除')
                    if action=='replace':
                        interval=decision['new_range'] or item['range'];self.valid_range(take,interval)
                        item.update(take_id=take['take_id'],media=copy.deepcopy(take['media']),range=interval)
                    if action=='exclude':item['included']=False
                    edit['handled_updates'].append(dict(item_id=item['id'],offered_take_id=take['take_id'],offered_selection_revision=offered['selection_revision'],decision='replace' if action=='replace' else 'keep'))
                else:
                    if action not in ('add','exclude'):raise ValueError('新片段请选择添加或排除')
                    item=self.item(take);item['included']=action=='add'
                    if decision['new_range']:self.valid_range(take,decision['new_range']);item['range']=decision['new_range']
                    after=decision['insert_after_item_id']
                    if after and after not in edit['order']:raise ValueError('插入位置已不存在')
                    edit['items'].append(item);edit['order'].insert(edit['order'].index(after)+1 if after else len(edit['order']),item['id'])
            return list(seen),{}
        return self.c.mutate(pid,data,change)

    def source_view(self,pid,tid):
        from ..asset_library.generation_records import parameter_records
        p=self.c.get(pid,'movie');take=self.take(p,tid);snapshot=p['artifacts'].get(take['snapshot_id'],{})
        bundle=next((b for b in p['content']['source_bundles'] if b['bundle_id']==snapshot.get('source_bundle_id')),None)
        return dict(take=take,snapshot=snapshot,bundle=bundle,parameters=parameter_records(dict(manifest=dict(settings=snapshot.get('parameters'),segment=dict(actual_seed=snapshot.get('parameters',{}).get('actual_seed'))))),script_url=('#/p/'+bundle['script_project_id']+'?step=4&target='+bundle['segment_id']) if bundle else None,generation_url='#/p/'+pid+'?step=0&target='+take['movie_segment_id']+'&take='+tid)

    def ingest(self,pid,data):
        request_contract('IngestResult',data)
        def change(p):
            result=next((t for t in p.get('movie_takes',[]) if t['take_id']==data['result_id']),None)
            composite=result is None
            if composite:result=next((e for e in p.get('movie_exports',[]) if e['export_id']==data['result_id']),None)
            if not result or result.get('state','available')!='available':raise ValueError('请选择未移除的有效结果')
            path=self.execution.path(p,result)
            snapshot={} if composite else p['artifacts'][result['snapshot_id']]
            records=dict(actual_prompt=snapshot.get('actual_prompt_text'),manifest=dict(settings=snapshot.get('parameters'),segment=dict(actual_seed=snapshot.get('parameters',{}).get('actual_seed'))))
            if composite:
                records['selected_runs']=[]
                for part in result['manifest']['parts']:
                    selected=self.take(p,part['item']['take_id']);captured=p['artifacts'][selected['snapshot_id']]
                    records['selected_runs'].append(dict(candidate=selected['take_id'],segment=selected['movie_segment_id'],records=dict(actual_prompt=captured['actual_prompt_text'],manifest=dict(settings=captured['parameters'],segment=dict(actual_seed=captured['parameters'].get('actual_seed'))))))
            origin=dict(type='generated',mode='movie',project=pid,project_name=p['name'],candidate=data['result_id'],segment=result.get('movie_segment_id'),composite=composite,export_created=result.get('created_at') if composite else None,actual_prompt=snapshot.get('actual_prompt_text'),records=records,movie_snapshot=copy.deepcopy(snapshot),movie_manifest=copy.deepcopy(result.get('manifest',{}).get('export_manifest')))
            origin['movie_lineage']=copy.deepcopy(result.get('lineage',{})) if not composite else dict(parts=[dict(project=pid,run=part['item']['take_id']) for part in result['manifest']['parts']])
            asset=self.c.library.ingest(path,data['asset_title'],provenance=origin,key='movie-result:'+pid+':'+data['result_id'])
            result['library_asset']=asset['id'];return [asset['id']],{}
        return self.c.mutate(pid,data,change)
