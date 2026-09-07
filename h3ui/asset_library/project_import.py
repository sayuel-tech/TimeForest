"""Preview a complete input change, then copy and atomically publish its project snapshot."""
import copy
import hashlib
import json
import shutil
import time
from pathlib import Path

from .bindings import expand
from .media import digest, command, inspect
from .store import encode
from ..studio_store import Conflict
from ..generation.asset_adapter import adapter


class PreviewStore:
    """Transient asset view used by the existing project change planner."""
    def __init__(self, original, new_assets):
        self.original, self.new_assets = original, {a['id']: a for a in new_assets}
        self.plan = None

    def __getattr__(self, key):
        return getattr(self.original, key)

    def asset(self, pid, aid):
        return self.new_assets[aid] if aid in self.new_assets else self.original.asset(pid, aid)

    def stage(self, pid, revision, plan):
        self.plan = plan
        return 'preview-only'


class ProjectImport:
    def __init__(self, library, studio):
        self.lib, self.st = library, studio

    def plan(self, pid, data):
        st, lib = self.st, self.lib
        if st.jobs.is_busy(pid):
            raise Conflict('当前项目正在执行，待任务结束后再应用资产；其他项目仍可编辑')
        p = st.store.get(pid)
        if p['revision'] != data.get('revision'):
            raise Conflict('项目已变化，请保存编排后重新选择资产')
        root = lib.store.get(data['asset'], data.get('version'))
        if root.get('deleted'):
            raise ValueError('该资产已在回收站，请恢复后再建立新引用')
        owner = data.get('owner') or root['id']
        if not isinstance(owner, str) or len(owner) > 100:
            raise ValueError('角色实例标识不合法')
        bundle = expand(lib, root['id'], root['snapshot']['id'], owner)
        source = data.get('target') == 'source'
        role = str(data.get('subject', '1'))
        if not role.isdigit() or not 1 <= int(role) <= 99:
            raise ValueError('角色编号须为1～99')
        ad = adapter(p['mode'])
        new_assets, entries, errors = [], [], []
        overrides = data.get('entries', {})
        if set(overrides) - {x['key'] for x in bundle['entries']}:
            raise ValueError('选择包含未登记的绑定项')
        selected_entries = bundle['entries'][:1] if source else bundle['entries']
        for entry in selected_entries:
            selection = overrides.get(entry['key'], {})
            chosen = bool(selection.get('selected', entry['selected']))
            mid = selection.get('media', entry['selected_media'])
            selected = next((m for m in entry['media'] if m['id'] == mid), None)
            if not selected:
                raise ValueError('所选媒体不属于该固定资产版本')
            purpose = 'source' if source else selection.get('purpose', entry['purpose'])
            status = dict(state='direct', note='独立的换人源视频，确认后准备切片') if source else ad.classify(entry, selected, purpose)
            if entry.get('deleted'):
                status = dict(state='unsupported', note='绑定资产已在回收站；请恢复后引用，或本次取消这一项')
            if source and (p['mode'] != 'swap' or selected['meta']['kind'] != 'video'):
                status = dict(state='unsupported', note='只有换人模式能将视频作为源表演')
            row = dict(key=entry['key'], name=entry['name'], asset=entry['asset'], version=entry['version'], media=mid,
                       purpose=purpose, subject=role if purpose in ('character', 'face', 'costume', 'voice') else '',
                       selected=chosen, owner=owner, **status)
            entries.append(row)
            if not chosen:
                continue
            if status['state'] != 'direct':
                errors.append(entry['name'] + '：' + status['note'])
                continue
            obj = lib.store.object(selected['hash'])
            use_range = data.get('range') if source else None
            if use_range:
                start, end = float(use_range['start']), float(use_range['end'])
                if not 0 <= start < end <= obj.get('duration', 0) + .01:
                    raise ValueError('源视频使用区间超出原件')
                use_range = {'start': start, 'end': end, 'time_base': obj.get('time_base')}
            identity = dict(asset=entry['asset'], version=entry['version'], media=mid, purpose=purpose,
                            subject=row['subject'], owner=owner, range=use_range)
            aid = hashlib.sha256((pid + encode(identity)).encode()).hexdigest()[:32]
            suffix = '.wav' if obj['kind'] == 'audio' else '.mp4' if use_range else obj['extension']
            target = st.store.directory(pid) / 'assets' / 'library' / (aid + suffix)
            projected = dict(id=aid, project=pid, name=entry['name'], kind=obj['kind'], purpose=purpose, subject=row['subject'],
                             path=str(target), input_name=f'time_forest_v5/{pid}/{aid}{suffix}', sha256=obj['hash'], bytes=obj['bytes'],
                             **{k: obj[k] for k in ('duration', 'width', 'height', 'has_audio') if k in obj},
                             library_reference={**identity, 'hash': obj['hash'], 'root_asset': root['id'], 'root_version': root['snapshot']['id']}, owners=[owner],
                             _library_source=dict(path=str(lib.store.path(obj['path'])), hash=obj['hash'], range=use_range))
            new_assets.append(projected)
        if not new_assets and not errors:
            errors.append('请选择至少一项媒体；取消选择不会改变当前素材')
        q = copy.deepcopy(p)
        summary = []
        if source:
            if len(new_assets) != 1 and not errors:
                errors.append('一次请选择一个源视频')
            if new_assets:
                q.update(source_asset=new_assets[0]['id'], source_candidate=new_assets[0]['id'], source_ready=False, status='draft', error=None, export=None)
            summary.append('将所选库视频作为新源，原视频与既有结果保留；确认后开始本地切片准备')
            staged = dict(project=q, summary=summary, affected=[])
        else:
            seg = next((s for s in q['segments'] if s['id'] == data.get('segment')), None)
            if seg is None:
                raise ValueError('片段不存在，请先准备源视频或片段')
            original = self.st.resolve(p, next(s for s in p['segments'] if s['id'] == seg['id']))
            replace = set(data.get('replace', []))
            if replace - {a['id'] for a in original}:
                raise ValueError('待替换素材不在本段引用中')
            retained = [a for a in original if a['id'] not in replace]
            images = [a for a in retained + new_assets if a['kind'] == 'image']
            audios = [a for a in retained + new_assets if a['kind'] == 'audio']
            if len(images) > ad.max_images:
                errors.append(f'当前模式最多{ad.max_images}张参考图。请取消额外绑定图，或明确选择替换已有图')
            if len(audios) > 3 or sum(a.get('duration', 0) for a in audios) > 15.05:
                errors.append('参考声音超过3项或总时长15秒；请取消部分声音或先裁切')
            if p['mode'] == 'swap' and audios and p['settings']['audio_policy'] == 'source':
                if data.get('audio_policy') == 'native':
                    q['settings']['audio_policy'] = 'native'
                    summary.append('声音策略将由源视频原声改为模型生成，仅参考声线与说话方式')
                else:
                    errors.append('当前保留源视频原声，无法同时引用新声线；请选择模型生成声音，或取消声线引用')
            seg.update(assets=list(dict.fromkeys([a['id'] for a in retained + new_assets])), inherit_ids=[], asset_mode='custom')
            if not errors:
                sandbox = copy.copy(st)
                sandbox.store = PreviewStore(st.store, new_assets)
                result = sandbox.edit_plan(pid, q)
                staged = sandbox.store.plan
                summary += result['summary']
                staged['summary'] = summary
            else:
                staged = dict(project=q, summary=summary, affected=[])
        if errors:
            return dict(ready=False, errors=errors, entries=entries, summary=summary, contract=ad.contract(p['settings']['recipe']))
        staged.update(assets_to_add=new_assets, library_import=True, source_import=source,
                      library_root=dict(asset=root['id'], version=root['snapshot']['id'], owner=owner))
        token = st.store.stage(pid, p['revision'], staged)
        return dict(ready=True, token=token, errors=[], entries=entries, summary=staged['summary'],
                    settings=staged['project']['settings'], contract=ad.contract(staged['project']['settings']['recipe']),
                    note='确认后托管项目副本。资产PROMPT、设定和绑定资料不进入工作流。')

    def apply(self, data, progress):
        pid, token = data['project'], data['token']
        st, lib = self.st, self.lib
        with st.store.connect() as db:
            row = db.execute('SELECT revision,body,expires,applied FROM changes WHERE token=? AND project=?', (token, pid)).fetchone()
        if not row:
            raise ValueError('资产引用方案不存在')
        revision, body, expires, applied = row
        plan = json.loads(body)
        if not plan.get('library_import'):
            raise ValueError('不是资产引用方案')
        if not applied:
            if expires < time.time() or st.store.get(pid)['revision'] != revision:
                raise Conflict('项目已变化或方案超时，请重新预览资产引用')
            for i, asset in enumerate(plan['assets_to_add']):
                progress(.05 + i / max(1, len(plan['assets_to_add'])) * .7, '准备项目内的独立素材副本')
                source = asset['_library_source']
                path, target = Path(source['path']), Path(asset['path'])
                if digest(path) != source['hash']:
                    raise ValueError('资产原件校验失败，未应用引用')
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    temp = target.with_name(target.stem + '.pending' + target.suffix)
                    if asset['kind'] == 'audio':
                        command(['ffmpeg', '-y', '-v', 'error', '-i', path, '-vn', '-ar', '32000', '-ac', '2', temp])
                    elif source.get('range'):
                        r = source['range']
                        command(['ffmpeg', '-y', '-v', 'error', '-ss', r['start'], '-i', path, '-t', r['end'] - r['start'],
                                 '-map', '0:v:0', '-map', '0:a?', '-c:v', 'libx264', '-crf', '18', '-fps_mode', 'passthrough', '-c:a', 'aac', '-movflags', '+faststart', temp], 3600)
                    else:
                        shutil.copyfile(path, temp)
                    temp.replace(target)
                asset.update(sha256=digest(target), bytes=target.stat().st_size)
                if asset['kind'] in ('audio', 'video'):
                    actual = inspect(target)
                    asset.update(duration=actual['duration'], has_audio=actual.get('has_audio'))
            with st.store.connect() as db:
                db.execute('UPDATE changes SET body=? WHERE token=? AND applied=0', (encode(plan), token))
            st.store.apply(pid, token)
        # Cross-store completion is idempotent: the project transaction has already committed.
        with lib.store.connect() as db:
            for asset in plan['assets_to_add']:
                ref = asset['library_reference']
                db.execute('INSERT OR REPLACE INTO refs VALUES(?,?,?,?,?)', (pid + ':' + asset['id'], ref['asset'], ref['version'], pid, encode(ref)))
                db.execute('UPDATE assets SET used=? WHERE id=?', (time.time(), ref['asset']))
        progress(1, '项目已引用固定版本素材')
        return dict(project=pid, revision=st.store.get(pid)['revision'], source_asset=plan['assets_to_add'][0]['id'] if plan['source_import'] else None)
