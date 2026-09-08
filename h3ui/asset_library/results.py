"""Register exact project media and results; client requests cannot supply file paths."""
import hashlib
import json
import time
from pathlib import Path

from .store import encode


class ResultImports:
    def __init__(self, library, studio):
        self.lib, self.st = library, studio

    def outputs(self, pid):
        p = self.st.store.get(pid)
        result = []

        def run_records(attempt):
            directory = Path(attempt.get('directory', '')).resolve()
            records = {'source_lineage': attempt['source_lineage']} if isinstance(attempt.get('source_lineage'),dict) else {}
            if self.st.store.directory(pid).resolve() not in directory.parents:
                return records
            for filename, key in [('manifest.json', 'manifest'), ('workflow.json', 'prompt')]:
                source = directory / filename
                if source.is_file() and self.st.store.directory(pid).resolve() in source.resolve().parents:
                    try:
                        records[key] = json.loads(source.read_text(encoding='utf-8'))
                    except (OSError, ValueError):
                        pass
            prompt = directory / 'prompt.txt'
            if prompt.is_file() and self.st.store.directory(pid).resolve() in prompt.resolve().parents:
                records['actual_prompt'] = prompt.read_text(encoding='utf-8')
            if attempt.get('tasks'):
                records['tasks'] = [dict(index=t.get('index'), selected=t.get('selected'), runs=[
                    dict(id=a['id'], seed=a.get('seed'), records=run_records(a))
                    for a in t.get('attempts', []) if a['id'] == t.get('selected')]) for t in attempt['tasks']]
            return records

        def register(kind, identifier, name, path, provenance):
            if not path:
                return
            file = Path(path).resolve()
            root = self.st.store.directory(pid).resolve()
            if root not in file.parents or not file.is_file():
                return
            stat = file.stat()
            if not stat.st_size:
                return
            token = hashlib.sha256(f'{pid}|{kind}|{identifier}|{file}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()
            payload = dict(project=pid, path=str(file), size=stat.st_size, mtime=stat.st_mtime_ns,
                           provenance=provenance, name=name)
            with self.lib.store.connect() as db:
                db.execute('INSERT OR IGNORE INTO operations VALUES(?,?,?,?,?)', (token, 'project_output', 'registered', encode(payload), time.time()))
            result.append(dict(id=token, kind=kind, result_id=identifier, name=name, bytes=stat.st_size,
                               url=self.st.url(pid, file), project=pid))

        def with_receipts():
            keys = {item['id']: ('assembly-output:'+pid+':'+item['result_id']) if p['mode']=='video_assembly' else 'project-output:'+item['id'] for item in result}
            receipts = self.lib.store.import_receipts(keys.values())
            for item in result:
                item.update(receipts.get(keys[item['id']], {}))
            return result

        if p['mode']=='video_assembly':
            available={e['id'] for c in p['assembly']['clips'] if not c.get('removed_at') for e in c['extensions'] if not e.get('removed_at')}
            for run in p['assembly']['runs']:
                if run['kind']=='generate' and run.get('extension') not in available:continue
                if run['state']=='success' and not run.get('removed_at') and run['kind'] in ('generate','export'):
                    register('candidate' if run['kind']=='generate' else 'final',run['id'],p['name']+' · '+('续接' if run['kind']=='generate' else '成片'),run.get('file'),dict(type='generated',project=pid,candidate=run['id'],mode=p['mode'],seed=run.get('seed'),snapshot=run['snapshot'],tasks=run['tasks']))
            return with_receipts()
        for asset in self.st.store.assets(pid):
            path = Path(asset['path'])
            originals = list(path.parent.glob('original.*'))
            if len(originals) == 1 and originals[0].is_file():
                path = originals[0]
            register('asset', asset['id'], asset['name'], path, dict(type='project', project=pid,
                      project_asset=asset['id'], library_reference=asset.get('library_reference')))
        for shot in p['segments']:
            for attempt in shot.get('attempts', []):
                if not attempt.get('delivery') or attempt.get('removed_at'):
                    continue
                provenance = dict(type='generated', project=pid, project_name=p['name'], segment=shot['id'],
                                  candidate=attempt['id'], seed=attempt.get('seed'), records=run_records(attempt))
                provenance['actual_prompt'] = provenance['records'].get('actual_prompt', '')
                register('candidate', attempt['id'], f'{p["name"]} · P{shot["index"]+1} · {attempt["id"][:8]}', attempt['delivery'], provenance)
        if p.get('export'):
            output = p['export']
            path = Path(output['file'])
            manifest = path.parent / 'manifest.json'
            try:
                records = json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() and self.st.store.directory(pid).resolve() in manifest.resolve().parents else None
            except (OSError, ValueError):
                records = None
            selected_ids = {x.get('attempt') for x in records.get('selected', [])} if isinstance(records, dict) else set()
            selected_runs = [dict(segment=s['id'], candidate=a['id'], records=run_records(a))
                             for s in p['segments'] for a in s.get('attempts', []) if a['id'] in selected_ids]
            register('final', str(output.get('created')), p['name'] + ' · 成片', path,
                     dict(type='generated', project=pid, project_name=p['name'], composite=True, export_created=output.get('created'), records={'segments': records, 'selected_runs': selected_runs},
                          metadata_status='present' if records else 'absent'))
        return with_receipts()

    def import_result(self, data, progress):
        with self.lib.store.connect() as db:
            row = db.execute("SELECT body FROM operations WHERE key=? AND type='project_output'", (data['output'],)).fetchone()
        if not row:
            raise ValueError('未登记的项目结果，请重新选择')
        source = json.loads(row[0])
        path = Path(source['path'])
        if not path.is_file() or path.stat().st_size != source['size'] or path.stat().st_mtime_ns != source['mtime']:
            raise ValueError('所选原结果已变化或缺失，请重新检查；不会替换成最新候选')
        provenance = source['provenance']
        if provenance.get('candidate'):
            project=self.st.store.get(source['project'])
            candidate=next((a for a in project['assembly']['runs'] if a['id']==provenance['candidate']),None) if project['mode']=='video_assembly' else next((a for s in project['segments'] for a in s.get('attempts',[]) if a['id']==provenance['candidate']),None)
            if candidate and project['mode']=='video_assembly' and candidate['kind']=='generate':
                available={e['id'] for c in project['assembly']['clips'] if not c.get('removed_at') for e in c['extensions'] if not e.get('removed_at')}
                if candidate.get('extension') not in available:raise ValueError('请先恢复所属片段和续写段')
            if not candidate or candidate.get('removed_at'):
                raise ValueError('候选已移除，请先恢复后重新选择入库')
        metadata = {'record_prompt': provenance.get('actual_prompt', ''), **data.get('metadata', {})}
        return self.lib.ingest(path, data.get('name') or source['name'], metadata, provenance,
                               key=('assembly-output:'+source['project']+':'+provenance['candidate']) if provenance.get('mode')=='video_assembly' else 'project-output:' + data['output'], progress=progress)
