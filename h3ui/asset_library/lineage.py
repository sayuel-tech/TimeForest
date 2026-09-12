"""Bounded upstream traversal of saved identities, never current selections or paths.

Usage registrations are intentionally not edges. Portable packs have a different
identity scope and must not resolve their old IDs against this installation.
"""
from urllib.parse import urlencode
from .generation_records import parameter_records
from .pack_lineage import media_origin


def mapping(value):
    return value if isinstance(value, dict) else {}


class AssetLineage:
    MAX_NODES = 64
    MAX_DEPTH = 16

    def __init__(self, origins, return_ref):
        self.origins = origins
        self.return_ref = return_ref
        self.rows = []
        self.truncated = False
        self.projects = {}

    def read(self, origin):
        self.expand(mapping(origin), None, (), 0)
        return dict(version=1, rows=self.rows, truncated=self.truncated)

    def row(self, relation, parent, **values):
        if len(self.rows) >= self.MAX_NODES:
            self.truncated = True
            return None
        result = dict(id=len(self.rows)+1, parent=parent, relation=relation, state='available', **values)
        self.rows.append(result)
        return result

    def project(self, pid, **target):
        project = self.origins.project(pid)
        if project and project['state'] == 'available':
            fields = {k:v for k,v in target.items() if isinstance(v,str) and v}
            fields.update(self.return_ref)
            project['url'] += '?' + urlencode({'origin_'+k:v for k,v in fields.items()})
        return project

    def follow(self, kind, ref, pid, relation, parent, trail, depth):
        ref = mapping(ref)
        identity = (kind, pid, ref.get('run'), ref.get('output'), ref.get('segment'), ref.get('internal_run'), ref.get('internal_segment')) if kind != 'asset' else (kind, *(ref.get(k) for k in ('asset','version','media','hash')))
        row = self.row(relation, parent, kind=kind)
        if row is None:
            return
        if depth >= self.MAX_DEPTH:
            row.update(state='limit', notice='来源链较长，已停止展开'); self.truncated=True; return
        if identity in trail:
            row.update(state='cycle', notice='来源记录存在循环，已停止追溯'); return
        trail = (*trail, identity)
        try:
            if kind == 'asset':
                if not all(isinstance(ref.get(k),str) and ref[k] for k in ('asset','version','media','hash')):
                    row.update(state='incomplete', notice='固定版本身份不完整，未推测来源'); return
                row.update({k:ref[k] for k in ('asset','version','media')})
                item = self.origins.lib.store.get(ref['asset'],ref['version'])
                snap = item['snapshot']
                media = next((m for m in snap['media'] if m['id']==ref['media'] and m['hash']==ref['hash']),None)
                if media is None:
                    row.update(state='missing', notice='固定版本媒体不存在或摘要不匹配'); return
                row.update(name=snap['name'], state='removed' if item.get('deleted') else 'available')
                origin = media_origin(snap,media)
                self.expand(mapping(origin),row['id'],trail,depth+1)
            elif kind == 'image':
                oid = ref.get('output')
                if not isinstance(pid,str) or not pid or not isinstance(oid,str) or not oid:
                    row.update(state='incomplete', notice='上游图片身份不完整'); return
                row.update(output=oid, project=self.project(pid,output=oid))
                images = self.origins.images
                if not images: raise KeyError('图片服务不可用')
                out = images.store.get('outputs',oid,pid)
                run = images.store.get('runs',out['run'],pid)
                task = images.store.get('tasks',out['task'],pid)
                row.update(run=run['id'], task=out['task'],
                           project=self.project(pid,output=oid,run=run['id'],task=out['task']),
                           state='removed' if out.get('removed_at') or task.get('discarded_at') else 'available')
                origin=dict(type='generated_image',project=pid,records=run)
                row['parameters']=parameter_records(origin)
                self.expand(origin,row['id'],trail,depth+1)
            elif kind == 'video':
                from ..generation.source_lineage import find_attempt, attempt_records
                if not all(isinstance(v,str) and v for v in (pid,ref.get('run'),ref.get('segment'))):
                    row.update(state='incomplete',notice='上游片段候选身份不完整');return
                row.update(run=ref.get('internal_run') or ref['run'],segment=ref['segment'],
                           project=self.project(pid,run=ref['run'],segment=ref['segment']))
                project=self.origins.studio.store.get(pid,include_deleted=True)
                if project.get('mode') not in ('swap','image_story','text_story'):raise KeyError('非原视频模式')
                attempt,historical,removed=find_attempt(project,ref)
                row.update(state='removed' if removed else 'historical' if historical else 'available')
                captured=dict(type='generated',project=pid,records=attempt_records(self.origins.studio.store,pid,attempt))
                row['parameters']=parameter_records(captured)
                self.expand(captured,row['id'],trail,depth+1)
            elif kind == 'movie':
                if not isinstance(pid,str) or not isinstance(ref.get('run'),str):raise KeyError('电影来源身份缺失')
                project=self.origins.studio.store.get(pid,include_deleted=True)
                if project.get('mode')!='movie':raise KeyError('并非电影项目')
                take=next(t for t in project.get('movie_takes',[]) if t['take_id']==ref['run'])
                snapshot=project['artifacts'][take['snapshot_id']]
                row.update(run=take['take_id'],segment=take['movie_segment_id'],project=self.project(pid,run=take['take_id'],segment=take['movie_segment_id']),state='removed' if take['state']=='removed' else 'available')
                captured=dict(mode='movie',project=pid,movie_lineage=take.get('lineage',{}),records=dict(manifest=dict(settings=snapshot['parameters'],segment=dict(actual_seed=snapshot['parameters'].get('actual_seed')))))
                row['parameters']=parameter_records(captured);self.expand(captured,row['id'],trail,depth+1)
            elif kind == 'assembly':
                rid=ref.get('run')
                if not isinstance(pid,str) or not pid or not isinstance(rid,str) or not rid:
                    row.update(state='incomplete', notice='上游续接身份不完整'); return
                row.update(run=rid,project=self.project(pid,run=rid))
                if pid not in self.projects:
                    self.projects[pid]=self.origins.studio.store.get(pid,include_deleted=True)
                project=self.projects[pid]
                if project.get('mode')!='video_assembly': raise KeyError('并非接续项目')
                assembly=project['assembly']
                run=next((r for r in assembly['runs'] if r['id']==rid),None)
                if run is None: raise KeyError('续接记录不存在')
                removed=bool(run.get('removed_at'))
                for clip in assembly.get('clips',[]):
                    for extension in clip.get('extensions',[]):
                        if extension['id']==run.get('extension'):
                            removed=removed or bool(clip.get('removed_at') or extension.get('removed_at'))
                row['state']='removed' if removed else 'available'
                origin=dict(type='generated',mode='video_assembly',project=pid,snapshot=run.get('snapshot'),seed=run.get('seed'),tasks=run.get('tasks'))
                row['parameters']=parameter_records(origin)
                self.expand(origin,row['id'],trail,depth+1)
        except (KeyError, ValueError, StopIteration):
            row.update(state='missing',notice='上游记录已不存在或身份不匹配，未替换为当前结果')

    def input(self, ref, pid, relation, parent, trail, depth):
        ref=mapping(ref)
        if any(k in ref for k in ('asset','version','media')):
            self.follow('asset',ref,None,relation,parent,trail,depth)
        elif ref.get('candidate'):
            self.follow('assembly',dict(run=ref['candidate']),pid,relation,parent,trail,depth)
        elif ref.get('parent_output'):
            self.follow('image',dict(output=ref['parent_output']),pid,relation,parent,trail,depth)
        else:
            row=self.row(relation,parent,kind='local')
            if row is not None: row.update(state='unrecorded',notice='本地输入或未记录可追溯身份')

    def expand(self, origin, parent, trail, depth):
        if len(self.rows)>=self.MAX_NODES:
            self.truncated=True; return
        pid=origin.get('project')
        if origin.get('mode')=='movie':
            lineage=mapping(origin.get('movie_lineage'))
            for ref in lineage.get('inputs',[]):self.follow('asset',ref,None,'reference',parent,trail,depth)
            previous=lineage.get('previous')
            if previous:self.follow('movie',previous,previous.get('project'),'continuation',parent,trail,depth)
            for index,ref in enumerate(lineage.get('parts',[])):self.follow('movie',ref,ref.get('project'),'part_'+str(index+1),parent,trail,depth)
            return
        if origin.get('type')=='portable_pack':
            row=self.row('pack',parent,kind='boundary')
            if row is None:return
            if origin.get('pack_lineage_version')!=1:
                row.update(state='external',notice='外部素材包身份未映射到本机，不关联同名或同编号项目');return
            row.update(state='pack',notice='素材包来源；仅映射包内固定资产，不关联外部项目')
            for link in origin.get('pack_links',[]):
                if link.get('state')=='mapped':
                    self.follow('asset',link.get('reference'),None,link.get('relation','ancestor'),row['id'],trail,depth+1)
                else:
                    missing=self.row(link.get('relation','ancestor'),row['id'],kind='boundary')
                    if missing is not None:missing.update(state='external',notice='此来源未随素材包提供')
            if origin.get('pack_lineage_incomplete'):
                row.update(state='unrecorded',notice='素材包中部分来源未记录完整；仅显示已确认关系')
            return
        if isinstance(origin.get('parent'),dict):
            self.follow('asset',origin['parent'],None,'derived',parent,trail,depth)
        if origin.get('type')=='project' and isinstance(origin.get('library_reference'),dict):
            self.follow('asset',origin['library_reference'],None,'derived',parent,trail,depth)
        if origin.get('type')=='generated_image':
            snapshot=mapping(mapping(origin.get('records')).get('snapshot'))
            # parent_output on a task can survive replacing A; only executed inputs
            # prove what actually became the source of this particular output.
            if snapshot.get('submode')=='text': return
            inputs=mapping(snapshot.get('inputs'))
            roles=['A']+(list('BCDEFGHI') if snapshot.get('submode')=='dual' else [])+(['mask'] if snapshot.get('submode')=='region' else [])
            for role in roles:
                if role in inputs:
                    self.input(mapping(inputs[role]).get('provenance'),pid,'image_'+role,parent,trail,depth)
            if not inputs:
                row=self.row('image_A',parent,kind='boundary')
                if row is not None: row.update(state='unrecorded',notice='此运行未保存输入来源快照，未从当前任务补齐')
            return
        snapshot=mapping(origin.get('snapshot'))
        if isinstance(snapshot.get('source'),dict):
            self.input(snapshot['source'].get('origin'),pid,'continuation',parent,trail,depth)
        parts=snapshot.get('parts')
        if isinstance(parts,list):
            for i,part in enumerate(parts):
                if not isinstance(part,dict): continue
                ref=dict(candidate=part['candidate']) if part.get('candidate') else part.get('origin')
                self.input(ref,pid,'part_'+str(i+1),parent,trail,depth)
                if len(self.rows)>=self.MAX_NODES: self.truncated=True; break
        records=mapping(origin.get('records'))
        # Original video modes persist per-shot records with the final export.
        # Their captured selected list is authoritative, not today's selections.
        selected=mapping(records.get('segments')).get('selected')
        saved=records.get('selected_runs')
        if isinstance(selected,list) and isinstance(saved,list):
            for i,part in enumerate(selected):
                if not isinstance(part,dict): continue
                rid=part.get('attempt')
                matches=[r for r in saved if isinstance(r,dict) and r.get('candidate')==rid and isinstance(rid,str) and rid]
                row=self.row('part_'+str(i+1),parent,kind='video')
                if row is None: break
                if len(matches)!=1 or not isinstance(matches[0].get('segment'),str):
                    row.update(state='incomplete',notice='成片的片段身份不完整或不唯一'); continue
                source=matches[0]
                row.update(run=rid,segment=source['segment'],project=self.project(pid,run=rid,segment=source['segment']))
                captured=dict(type='generated',project=pid,records=source.get('records'))
                row['parameters']=parameter_records(captured)
                if depth>=self.MAX_DEPTH:
                    row.update(state='limit',notice='来源链较长，已停止展开');self.truncated=True
                else:self.expand(captured,row['id'],trail,depth+1)
        manifest=mapping(records.get('manifest'))
        sources=records.get('source_lineage',manifest.get('source_lineage'))
        if isinstance(sources,dict) and sources.get('version')==1:
            for source in sources.get('inputs',[]):
                if not isinstance(source,dict):continue
                self.input(source.get('reference'),pid,'reference_'+str(source.get('kind','unknown')),parent,trail,depth)
                if len(self.rows)>=self.MAX_NODES:self.truncated=True;break
            previous=sources.get('previous')
            if isinstance(previous,dict):
                self.follow('video',previous,previous.get('project'), 'continuation',parent,trail,depth)
            elif sources.get('previous_recorded') is False:
                row=self.row('continuation',parent,kind='boundary')
                if row is not None:row.update(state='unrecorded',notice='此运行的上游候选身份未记录')
        elif manifest.get('previous'):
            row=self.row('continuation',parent,kind='boundary')
            if row is not None: row.update(state='unrecorded',notice='旧视频运行仅保存上下文文件，未记录可核对的上游候选身份')
