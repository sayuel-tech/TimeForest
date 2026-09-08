"""Read-only, exact-media lineage. Never infer authorship from usage or filenames."""
from urllib.parse import quote, urlencode
from .generation_records import parameter_records
from .lineage import AssetLineage
from .pack_lineage import media_origin


class AssetOrigins:
    def __init__(self, library, studio, images=None):
        self.lib, self.studio, self.images = library, studio, images
        self.projects = {}

    def project(self, pid, recorded_name=None):
        if not isinstance(pid, str) or not pid:
            return None
        if pid not in self.projects:
            try:
                if self.images and self.images.store.exists(pid):
                    p = self.images.store.project(pid, deleted=True)
                else:
                    p = self.studio.store.get(pid, include_deleted=True)
                self.projects[pid] = dict(id=pid, name=p['name'], mode=p.get('mode', 'image_assets' if self.images and self.images.store.exists(pid) else ''), state='removed' if p.get('deleted_at') else 'available')
            except KeyError:
                self.projects[pid] = dict(id=pid, name=recorded_name or pid, state='missing')
        result = dict(self.projects[pid])
        result['recorded_name'] = recorded_name
        if result['state'] == 'available': result['url'] = '#/p/' + quote(pid, safe='')
        elif result['state'] == 'removed': result['url'] = '#/assets?view=trash&recycle=projects'
        return result

    def read(self, aid, version, mid):
        item = self.lib.store.get(aid, version)
        media = next((m for m in item['snapshot']['media'] if m['id'] == mid), None)
        if not media: raise ValueError('所选媒体不属于该资产版本')
        result = dict(version=1, generation_descendants_version=1, chain=[], parameters=[], prompt='', parts=[])
        visited = set()
        for depth in range(16):
            snap = item['snapshot']
            identity = (item['id'], snap['id'], media['id'])
            if identity in visited:
                result['notice'] = '来源记录存在循环，已停止追溯'; break
            visited.add(identity)
            origin = media_origin(snap,media)
            row = dict(asset=item['id'], version=snap['id'], media=media['id'], name=snap['name'],
                       removed=bool(item.get('deleted')), type=origin.get('type', 'unknown'),
                       operation=origin.get('operation'), project=None if origin.get('type')=='portable_pack' else self.project(origin.get('project'), origin.get('project_name')),
                       task=origin.get('task'), segment=origin.get('segment'), run=origin.get('run') or origin.get('candidate'),
                       output=origin.get('output'))
            if row['project'] and row['project']['state']=='available':
                target = {k:v for k,v in dict(run=row['run'], task=row['task'], output=row['output'], segment=row['segment'],
                          final=str(origin.get('export_created', 'unknown')) if origin.get('composite') else None).items() if isinstance(v, str) and v}
                if target:
                    target.update(asset=row['asset'], version=row['version'], media=row['media'])
                    row['project']['url'] += '?' + urlencode({'origin_'+k:v for k,v in target.items()})
            result['chain'].append(row)
            # Parameters belong ONLY to the requested media, never its parent/current project.
            if depth == 0:
                result['lineage'] = AssetLineage(self,dict(asset=row['asset'],version=row['version'],media=row['media'])).read(origin)
                result['parameters'] = parameter_records(origin)
                result['prompt'] = origin.get('actual_prompt') if isinstance(origin.get('actual_prompt'), str) else ''
                snapshot = origin.get('snapshot') if isinstance(origin.get('snapshot'), dict) else {}
                source = snapshot.get('source', {})
                if isinstance(source, dict) and isinstance(source.get('origin'), dict):
                    row['previous_run'] = source['origin'].get('candidate')
                parts = snapshot.get('parts', [])
                if isinstance(parts, list):
                    result['parts'] = [dict(index=i+1, run=p.get('candidate'), start=p.get('start'), end=p.get('end'))
                                       for i, p in enumerate(parts) if isinstance(p, dict)]
                records = origin.get('records', {})
                manifest = records.get('segments') if isinstance(records, dict) else None
                if isinstance(manifest, dict) and isinstance(manifest.get('selected'), list):
                    result['parts'] = [dict(index=i+1, run=p.get('attempt')) for i,p in enumerate(manifest['selected']) if isinstance(p,dict)]
            parent = origin.get('parent')
            if not isinstance(parent, dict): break
            if not all(isinstance(parent.get(k), str) and parent[k] for k in ('asset','version','media','hash')):
                result['notice'] = '父资产固定版本记录不完整，未推测来源'; break
            try:
                item = self.lib.store.get(parent['asset'], parent['version'])
                media = next((m for m in item['snapshot']['media'] if m['id']==parent['media'] and m['hash']==parent['hash']), None)
                if not media: raise KeyError('父媒体不匹配')
            except KeyError:
                result['notice'] = '父资产版本或媒体已不存在，保留现有来源记录'; break
        else:
            result['notice'] = '来源链较长，已显示前16层'
        return result
