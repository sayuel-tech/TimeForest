"""Authoring content lives in StudioStore projects, with explicit versioned writes."""
import copy
import time
import uuid
from .contracts import digest, request_contract, read, validate
from ..studio_store import Conflict


def uid():
    return uuid.uuid4().hex


LAYERS = ('intent','screenplay','asset_bindings','asset_screenplay','storyboard','segment','visual_references','prompt')
COLLECTIONS = {'screenplay':'blocks','asset_screenplay':'blocks','storyboard':'shots',
               'segment':'segments','visual_references':'references'}


class Creation:
    def __init__(self, studio, library=None):
        self.st, self.store, self.library = studio, studio.store, library
        from .writing import Writing
        self.writing=Writing(self)
        from .references import References
        self.references=References(self)
        from .movie import Movie
        self.movie=Movie(self)
        # Only change local status markers on startup; never reconnect/replay work.
        for project in self.store.list():
            if project.get('mode') not in ('authoring','movie'):continue
            changed=False
            for job in project.get('creation_jobs',[]):
                if job['state'] in ('queued','preparing','submitting','running','cancel_requested'):
                    uncertain=job['state'] in ('submitting','running') and (job.get('provider_request_id') or job['kind']!='media_export')
                    job.update(state='submission_unknown' if uncertain else 'failed',phase='上次处理已中断；未自动重放',failure_code='PROCESS_INTERRUPTED',event_seq=job['event_seq']+1,updated=time.time());changed=True
            if changed:self.store.save(project,project['revision'])

    def get(self, pid, mode=None):
        p = self.store.get(pid)
        if p.get('mode') not in ('authoring','movie') or (mode and p['mode']!=mode):
            raise ValueError('项目类型不匹配')
        return p

    def snapshot(self, pid):
        p=copy.deepcopy(self.get(pid))
        p.pop('_receipts',None)
        p.pop('_creation_key',None)
        p.pop('_creation_request',None)
        p['busy']=self.st.jobs.is_busy(pid)
        p['creation_contract_version']=1
        p['creation_experience_version']=2
        p['writing_draft_hashes']={k:digest(v) for k,v in p.get('writing_drafts',{}).items()}
        if p['mode']=='authoring':p['writing_target_hashes']={name+':'+item['ref']:self.layer_hash(p,name,[item['ref']]) for name,collection in [('storyboard','shots'),('segment','segments')] for item in (self.layer(p,name) or {}).get('content',{}).get(collection,[])}
        p['asset_library']=[self.st.public_asset(a) for a in self.store.assets(pid)]
        if p['mode']=='movie':
            p['edit_content_hash']=digest(p['content']['edit'])
            p['edit_seams']=self.movie.seams(p)
            for record in p.get('movie_media',{}).values():record['url']='/api/v5/projects/'+pid+'/files/'+record['relative_path']
        from .presentation import snapshot
        return snapshot(p)

    def create(self, mode, data):
        request_contract('CreateAuthoring' if mode=='authoring' else 'CreateMovie',data)
        with self.store.lock:
            for p in self.store.list():
                if p.get('_creation_key')==data['request_key']:
                    if p.get('_creation_request')!=data or p['mode']!=mode: raise Conflict('请求标识已用于不同创建内容')
                    self.capture(p['id'])
                    return self.snapshot(p['id'])
            if mode=='authoring':
                content=dict(layers=[],confirmations=[],source_links=[],job_ids=[])
            else:
                source=self.get(data['source_project_id'],'authoring')
                if source['revision']!=data['source_revision']: raise Conflict('来源剧本已更新')
                content=dict(source_project_id=source['id'],source_bundles=[],segment_order=[],generation_drafts=[],
                             adoptions=[],take_ids=[],job_ids=[],edit=dict(content_schema_version=1,initialized_at=None,items=[],order=[],handled_updates=[]))
                # Validate and freeze before inserting a project, so bad source
                # bindings cannot leave an orphan creation receipt behind.
                staged=dict(content=content,artifacts={})
                self.movie.import_source(staged,source,data['segment_ids'])
            p=self.store.create(dict(mode=mode,kind=mode,name=data['title'][:120],status='draft',duration=0,
                                     segments=[],settings={},content_schema_version=1,content=content,
                                     history=[],candidates=[],creation_jobs=[],artifacts={},_receipts={},
                                     _creation_key=data['request_key'],_creation_request=data))
            if mode=='movie':
                p['artifacts']=staged['artifacts']
                self.store.save(p,p['revision'])
                self.capture(p['id'])
            return self.snapshot(p['id'])

    def layer(self, p, name, targets=()):
        rows=p['content']['layers']
        found=next((x for x in rows if x['layer']==name and x['target_ids']==list(targets)),None)
        if found or not targets or name not in COLLECTIONS:return found
        root=self.layer(p,name)
        if not root:return None
        collection=COLLECTIONS[name];field='id' if collection=='references' else 'ref'
        content=copy.deepcopy(root['content'])
        content[collection]=[x for x in content.get(collection,[]) if x[field] in targets]
        return dict(layer=name,target_ids=list(targets),content=content,content_hash=digest(content))

    def layer_hash(self,p,name,targets=()):
        row=self.layer(p,name,targets)
        return row['content_hash'] if row else digest({})

    def mutate(self,pid,data,fn):
        with self.store.lock:
            p=self.get(pid); key=data['request_key']; signature=digest(data)
            previous=p['_receipts'].get(key)
            if previous:
                if previous['signature']!=signature: raise Conflict('请求标识已用于不同修改')
                return previous['result']
            if p['revision']!=data['revision']: raise Conflict('项目已更新；当前草稿保留，请重新核对')
            changed,id_map=fn(p)
            receipt=dict(project_id=pid,revision=p['revision']+1,receipt_id=uid(),changed_ids=changed,id_map=id_map)
            p['_receipts'][key]=dict(signature=signature,result=receipt)
            self.store.save(p,p['revision'])
        self.capture(pid)
        return receipt

    def capture(self,pid):
        p=self.get(pid)
        if p['mode']=='movie' and self.library:
            rows={}
            for sid in p['content']['segment_order']:
                _,source=self.movie.frozen(p,sid)
                for r in source['references']:rows[digest(r['library_reference'])[:32]]=r['library_reference']
            for take in p.get('movie_takes',[]):
                for fixed in take.get('lineage',{}).get('inputs',[]):rows[digest(fixed)[:32]]=fixed
            self.library.complete_usage(pid,[dict(id=rid,reference=fixed) for rid,fixed in rows.items()],'movie:'+pid+':'+str(p['revision']))
        library=getattr(self.st,'prompt_library',None)
        if library: return library.capture(p)

    def save(self,pid,data):
        request_contract('SaveAuthoring',data)
        self.get(pid,'authoring')
        return self.mutate(pid,data,lambda p:self.write_layer(p,data))

    def write_layer(self,p,data):
        name=data['layer']; targets=data['target_ids']; content=copy.deepcopy(data['content'])
        if name=='prompt' and len(targets)!=1: raise ValueError('正式 Prompt 必须指定一个片段')
        existing=self.layer(p,name,targets)
        expected=existing['content_hash'] if existing else None
        if data['base_content_hash']!=expected: raise Conflict('正文依据已变化，未覆盖当前内容')
        if targets and name in COLLECTIONS:
            if data['update_mode']!='merge_targets':raise ValueError('局部修改必须合并到指定内容')
            collection=COLLECTIONS[name];field='id' if collection=='references' else 'ref'
            changed={x[field] for x in content.get(collection,[])}|set(data['removed_target_ids'])
            if changed-set(targets):raise ValueError('局部修改超出指定内容')
            existing=self.layer(p,name)
        canonical_targets=[] if name in COLLECTIONS else targets
        id_map={}; collection=COLLECTIONS.get(name)
        if collection:
            rows=content.get(collection,[]); field='id' if collection=='references' else 'ref'
            old=(existing or {}).get('content',{}).get(collection,[])
            known={x[field] for x in old}
            for row in rows:
                key=row[field]
                if key.startswith('tmp:'):
                    id_map[key]=uid();row[field]=id_map[key]
                elif key not in known:
                    raise ValueError('新增内容须使用临时标识 tmp:，由网站分配身份')
            if len({x[field] for x in rows})!=len(rows): raise ValueError('内容标识重复')
            if data['update_mode']=='merge_targets':
                updates={x[field]:x for x in rows}
                content[collection]=[updates.pop(x[field],x) for x in old if x[field] not in data['removed_target_ids']]+list(updates.values())
            content=self.remap(content,id_map)
        if name=='asset_bindings':
            previous=(existing or {}).get('content',{})
            for array,field in [('needs','ref'),('bindings','id')]:
                old_ids={x[field] for x in previous.get(array,[])}
                for item in content.get(array,[]):
                    value=item[field]
                    if value.startswith('tmp:'):id_map[value]=uid()
                    elif value not in old_ids:raise ValueError('新增资产需求或绑定须由网站分配身份')
            content=self.remap(content,id_map)
            if data['update_mode']=='merge_targets':
                content['policies']={**previous.get('policies',{}),**content.get('policies',{})}
                for array,field in [('needs','ref'),('bindings','id')]:
                    updates={x[field]:x for x in content.get(array,[])}
                    content[array]=[updates.pop(x[field],x) for x in previous.get(array,[])]+list(updates.values())
        previous_content=copy.deepcopy(existing['content']) if existing else {}
        unchanged=existing is not None and digest(content)==existing['content_hash']
        if existing:
            p['history'].append(copy.deepcopy(existing))
            existing.update(content=content,content_hash=digest(content))
        else:
            p['content']['layers'].append(dict(layer=name,target_ids=canonical_targets,content=content,content_hash=digest(content)))
        self.check_relationships(p)
        if name=='intent': p['duration']=content.get('target_duration_seconds') or 0
        affected=set(targets)
        if name in ('segment','storyboard'):
            collection=COLLECTIONS[name];before={r['ref']:r for r in previous_content.get(collection,[])};after={r['ref']:r for r in content.get(collection,[])}
            affected={ref for ref in set(before)|set(after) if before.get(ref)!=after.get(ref)}
            if name=='storyboard':affected={s['ref'] for s in (self.layer(p,'segment') or {}).get('content',{}).get('segments',[]) if s['shot_ref'] in affected}
        for confirmation in p['content']['confirmations']:
            direct=confirmation['layer']==name and (name!='prompt' or confirmation['target_id'] in targets)
            if direct and name in ('storyboard','segment') and confirmation['target_id']!='project':
                current=self.layer(p,name,confirmation['target_id'].split(','))
                direct=not current or confirmation['content_hash']!=current['content_hash']
            dependents={'intent':{'screenplay','asset_bindings','asset_screenplay','storyboard','segment','prompt'},
                'screenplay':{'asset_bindings','asset_screenplay','storyboard','segment','prompt'},
                'asset_bindings':{'asset_screenplay','storyboard','segment','prompt'},
                'asset_screenplay':{'storyboard','segment','prompt'},'visual_references':{'prompt'}}
            downstream=confirmation['layer'] in dependents.get(name,set()) or name in ('storyboard','segment') and confirmation['layer']=='prompt' and confirmation['target_id'] in affected
            if name=='storyboard' and confirmation['layer']=='segment':downstream=confirmation['target_id']=='project' or confirmation['target_id'] in affected
            if not unchanged and (direct or downstream):
                confirmation['review_state']='review_required'
        if not unchanged:
            downstream=name+':'+','.join(canonical_targets)
            p['content']['source_links']=[x for x in p['content']['source_links'] if x['downstream_id']!=downstream]
            for source in p['content']['layers']:
                if source['layer']==name:continue
                p['content']['source_links'].append(dict(downstream_id=downstream,upstream_id=source['layer']+':'+','.join(source['target_ids']),upstream_hash=source['content_hash']))
        return list(id_map.values()) or targets or [name],id_map

    @staticmethod
    def remap(value,mapping):
        if isinstance(value,dict):return {k:Creation.remap(v,mapping) for k,v in value.items()}
        if isinstance(value,list):return [Creation.remap(v,mapping) for v in value]
        return mapping.get(value,value) if isinstance(value,str) else value

    def check_relationships(self,p):
        shots=(self.layer(p,'storyboard') or {}).get('content',{}).get('shots',[])
        segments=(self.layer(p,'segment') or {}).get('content',{}).get('segments',[])
        shot_ids={x['ref'] for x in shots}; segment_ids={x['ref'] for x in segments}
        parents={}
        for segment in segments:
            if segment['shot_ref'] not in shot_ids: raise ValueError('片段所属分镜不存在')
            dependency=segment.get('dependency',{})
            if dependency.get('kind')=='upstream_tail':
                parent=dependency.get('upstream_ref')
                if parent not in segment_ids: raise ValueError('续接上游片段不存在')
                parents[segment['ref']]=parent
        for start in parents:
            seen=set();current=start
            while current in parents:
                if current in seen: raise ValueError('续接关系存在循环')
                seen.add(current);current=parents[current]
        for row in p['content']['layers']:
            if row['layer']=='prompt' and any(x not in segment_ids for x in row['target_ids']):
                raise ValueError('正式 Prompt 对应片段不存在；请先处理相关 Prompt')
        bindings=(self.layer(p,'asset_bindings') or {}).get('content',{})
        needs={n['ref'] for n in bindings.get('needs',[])}
        characters={n['ref'] for n in bindings.get('needs',[]) if n['kind']=='character'}
        for need in bindings.get('needs',[]):
            if need.get('subject_ref') and need['subject_ref'] not in characters:raise ValueError('资产关联的角色需求不存在')
        if set(bindings.get('policies',{})) - ({p['id']}|shot_ids|segment_ids):raise ValueError('资产来源策略的对象不存在')
        for b in bindings.get('bindings',[]):
            if b['need_ref'] not in needs:raise ValueError('绑定的资产需求不存在')
            scope={'shot':shot_ids,'segment':segment_ids,'project':{p['id']}}.get(b['scope_kind'])
            if scope is not None and set(b['scope_ids'])-scope:raise ValueError('资产绑定的作用范围不存在')
            if b['state']=='bound':
                if not b['asset_ref'] or not b['asset_version']:raise ValueError('绑定须指定固定资产版本')
                if not self.library:raise ValueError('资产库未配置')
                self.library.store.get(b['asset_ref'],b['asset_version'])
                if b.get('reference_id'):
                    reference=next((r for r in p.get('creation_references',[]) if r['id']==b['reference_id']),None)
                    if not reference or reference['library_reference']['asset']!=b['asset_ref'] or reference['library_reference']['version']!=b['asset_version']:raise ValueError('绑定参考与固定资产版本不一致')

    def confirm(self,pid,data):
        request_contract('ConfirmContent',data)
        def apply(p):
            row=self.layer(p,data['layer'],data['target_ids'])
            if not row: raise ValueError('请先保存当前内容')
            if data['content_hashes'].get(data['layer'])!=row['content_hash']: raise Conflict('确认内容已变化')
            texts=[]
            def visit(x):
                if isinstance(x,dict):
                    for k,v in x.items():
                        if k in ('text','story_text','prompt_text','prompt') and isinstance(v,str): texts.append(v.strip())
                        else: visit(v)
                elif isinstance(x,list):
                    for v in x: visit(v)
            visit(row['content'])
            if data['layer']=='asset_bindings':
                from .bindings import resolve
                if any(b['state']=='pending' for b in resolve(self,p)):raise ValueError('仍有待落实的资产绑定')
            elif not any(texts): raise ValueError('请先填写需要确认的正文')
            target=','.join(data['target_ids']) or 'project'
            p['content']['confirmations']=[c for c in p['content']['confirmations'] if not(c['layer']==data['layer'] and c['target_id']==target)]
            p['content']['confirmations'].append(dict(layer=data['layer'],target_id=target,content_hash=row['content_hash'],
                confirmed_at=str(time.time()),review_state='current',basis_hashes=[r['content_hash'] for r in p['content']['layers'] if r is not row]))
            return [target],{}
        return self.mutate(pid,data,apply)
