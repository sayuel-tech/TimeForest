"""Indexed metadata and immutable versions, independent of project storage."""
import copy
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from ..studio_store import Conflict

SCHEMA_VERSION = 1
SYSTEM_CATEGORIES = {'character': '角色', 'scene': '场景', 'prop': '物品', 'costume': '服装',
                     'accessory': '饰品', 'voice': '声音', 'palette': '色系', 'video': '视频',
                     'control': '遮罩／控制参考', 'texture': '材质／纹理'}


def uid():
    return uuid.uuid4().hex


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


class LibraryStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'library.sqlite3'
        self.lock = threading.RLock()
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError('资产库版本高于当前网站，请使用匹配版本，不能覆盖数据库')
            db.executescript('''PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS assets(
                  id TEXT PRIMARY KEY, revision INTEGER NOT NULL, name TEXT NOT NULL,
                  version TEXT NOT NULL, kind TEXT, favorite INTEGER NOT NULL DEFAULT 0,
                  state TEXT DEFAULT 'candidate', deleted REAL, created REAL, updated REAL, used REAL,
                  source TEXT, width INTEGER, height INTEGER, duration REAL, fps REAL, has_audio INTEGER);
                CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY, asset TEXT NOT NULL,
                  created REAL NOT NULL, body TEXT NOT NULL, FOREIGN KEY(asset) REFERENCES assets(id) DEFERRABLE INITIALLY DEFERRED);
                CREATE INDEX IF NOT EXISTS versions_asset ON versions(asset, created);
                CREATE INDEX IF NOT EXISTS assets_updated ON assets(deleted, updated DESC);
                CREATE INDEX IF NOT EXISTS assets_media ON assets(kind, deleted, duration);
                CREATE TABLE IF NOT EXISTS objects(hash TEXT PRIMARY KEY, path TEXT NOT NULL, bytes INTEGER NOT NULL, meta TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS categories(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, system INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS asset_categories(asset TEXT, category TEXT, PRIMARY KEY(asset, category));
                CREATE INDEX IF NOT EXISTS by_category ON asset_categories(category, asset);
                CREATE TABLE IF NOT EXISTS tags(asset TEXT, tag TEXT, PRIMARY KEY(asset, tag));
                CREATE INDEX IF NOT EXISTS by_tag ON tags(tag, asset);
                CREATE TABLE IF NOT EXISTS collections(id TEXT PRIMARY KEY, name TEXT, description TEXT, revision INTEGER DEFAULT 1);
                CREATE TABLE IF NOT EXISTS collection_items(collection TEXT, asset TEXT, position INTEGER, PRIMARY KEY(collection, asset));
                CREATE TABLE IF NOT EXISTS operations(key TEXT PRIMARY KEY, type TEXT, state TEXT, body TEXT, updated REAL);
                CREATE TABLE IF NOT EXISTS refs(key TEXT PRIMARY KEY, asset TEXT, version TEXT, project TEXT, body TEXT);
                PRAGMA user_version=1;''')
            db.executemany('INSERT OR IGNORE INTO categories VALUES(?,?,1)', SYSTEM_CATEGORIES.items())

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_receipts(self, keys):
        """Read existing completed imports, including trash, without rewriting project data."""
        found = {}
        keys = list(set(keys))
        with self.connect() as db:
            for offset in range(0, len(keys), 500):
                batch = keys[offset:offset + 500]
                rows = db.execute("SELECT key,body FROM operations WHERE state='done' AND key IN (" + ','.join('?' for _ in batch) + ')', batch)
                candidates = {row['key']: json.loads(row['body']).get('asset') for row in rows}
                ids = list(set(a for a in candidates.values() if a))
                if not ids:
                    continue
                assets = {row['id']: row['deleted'] for row in db.execute('SELECT id,deleted FROM assets WHERE id IN (' + ','.join('?' for _ in ids) + ')', ids)}
                found.update({key: dict(asset=aid, asset_removed=bool(assets[aid])) for key, aid in candidates.items() if aid in assets})
        return found

    def path(self, relative):
        path = (self.root / relative).resolve()
        if self.root not in path.parents:
            raise ValueError('资产文件路径越界')
        return path

    def object(self, sha):
        with self.connect() as db:
            row = db.execute('SELECT * FROM objects WHERE hash=?', (sha,)).fetchone()
        if not row:
            raise KeyError('媒体对象不存在')
        return dict(hash=row['hash'], path=row['path'], bytes=row['bytes'], **json.loads(row['meta']))

    def objects(self, hashes):
        keys=list(set(hashes));result={}
        if not keys:return result
        with self.connect() as db:
            for offset in range(0,len(keys),500):
                batch=keys[offset:offset+500]
                rows=db.execute('SELECT * FROM objects WHERE hash IN ('+','.join('?' for _ in batch)+')',batch)
                result.update({r['hash']:dict(hash=r['hash'],path=r['path'],bytes=r['bytes'],**json.loads(r['meta'])) for r in rows})
        if len(result)!=len(keys):raise KeyError('媒体对象不存在')
        return result

    def get(self, aid, version=None):
        with self.connect() as db:
            row = db.execute('SELECT * FROM assets WHERE id=?', (aid,)).fetchone()
            if not row:
                raise KeyError('资产不存在')
            ver = db.execute('SELECT body FROM versions WHERE id=? AND asset=?', (version or row['version'], aid)).fetchone()
            if not ver:
                raise KeyError('资产版本不存在')
            snapshot = json.loads(ver[0])
            if version is None:
                snapshot['categories'] = [r[0] for r in db.execute('SELECT category FROM asset_categories WHERE asset=?', (aid,))]
            return {**dict(row), 'snapshot': snapshot,
                    'collections': [r[0] for r in db.execute('SELECT collection FROM collection_items WHERE asset=?', (aid,))]}

    def versions(self, aid):
        with self.connect() as db:
            return [dict(id=r['id'], created=r['created']) for r in db.execute('SELECT id,created FROM versions WHERE asset=? ORDER BY created DESC', (aid,))]

    def query(self, filters):
        page = max(1, int(filters.get('page', 1)))
        limit = min(100, max(1, int(filters.get('limit', 36))))
        where = ['a.deleted IS NOT NULL' if filters.get('trash') == '1' else 'a.deleted IS NULL']
        params = []
        for key, column in [('kind', 'kind'), ('source', 'source'), ('state', 'state')]:
            if filters.get(key):
                where.append(f'a.{column}=?'); params.append(filters[key])
        if filters.get('q'):
            where.append('a.name LIKE ?'); params.append('%' + str(filters['q'])[:200] + '%')
        if filters.get('contains_kind') in ('image','video','audio'):
            where.append("EXISTS(SELECT 1 FROM json_each(v.body,'$.media') m JOIN objects o ON o.hash=json_extract(m.value,'$.hash') WHERE json_extract(o.meta,'$.kind')=?)")
            params.append(filters['contains_kind'])
        if filters.get('favorite') == '1':
            where.append('a.favorite=1')
        if filters.get('unorganized') == '1':
            where.append('NOT EXISTS(SELECT 1 FROM asset_categories c WHERE c.asset=a.id)')
        category = filters.get('category')
        if category:
            predicate = 'EXISTS(SELECT 1 FROM asset_categories c WHERE c.asset=a.id AND c.category=?)'
            # Video is a system aggregate, also covering alternate media in a version.
            if category == 'video':
                predicate = "(" + predicate + " OR EXISTS(SELECT 1 FROM json_each(v.body,'$.media') m JOIN objects o ON o.hash=json_extract(m.value,'$.hash') WHERE json_extract(o.meta,'$.kind')='video'))"
            where.append(predicate); params.append(category)
        for key, table, column in [('tag', 'tags', 'tag'), ('collection', 'collection_items', 'collection')]:
            if filters.get(key):
                where.append(f'EXISTS(SELECT 1 FROM {table} t WHERE t.asset=a.id AND t.{column}=?)'); params.append(filters[key])
        for key, column, op in [('min_duration', 'duration', '>='), ('max_duration', 'duration', '<='),
                                ('min_width', 'width', '>='), ('max_width', 'width', '<='), ('min_fps', 'fps', '>='), ('max_fps', 'fps', '<=')]:
            if filters.get(key) not in (None, ''):
                where.append(f'a.{column}{op}?'); params.append(float(filters[key]))
        if filters.get('audio') in ('0', '1'):
            where.append('a.has_audio=?'); params.append(int(filters['audio']))
        if filters.get('aspect') in ('portrait', 'landscape', 'square'):
            where.append({'portrait': 'a.width<a.height', 'landscape': 'a.width>a.height', 'square': 'a.width=a.height'}[filters['aspect']])
        for key in ('model', 'lora'):
            if filters.get(key):
                where.append("json_extract(v.body,'$.provenance') LIKE ?"); params.append('%' + str(filters[key])[:200] + '%')
        if filters.get('image_tool') in ('single','dual','region','outpaint','text'):
            where.append("EXISTS(SELECT 1 FROM json_each(v.body,'$.media') m WHERE json_extract(m.value,'$.provenance.tool')=?)")
            params.append(filters['image_tool'])
        sql = ' FROM assets a JOIN versions v ON v.id=a.version WHERE ' + ' AND '.join(where)
        order = {'name': 'a.name,a.id', 'used': 'a.used DESC,a.updated DESC', 'oldest': 'a.created,a.id'}.get(filters.get('sort'), 'a.updated DESC,a.id')
        with self.connect() as db:
            total = db.execute('SELECT count(*)' + sql, params).fetchone()[0]
            rows = db.execute('SELECT a.*,v.body' + sql + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?', params + [limit, (page - 1) * limit]).fetchall()
            items = [{**{k: r[k] for k in r.keys() if k != 'body'}, 'snapshot': json.loads(r['body'])} for r in rows]
            categories={item['id']:[] for item in items}
            if items:
                for row in db.execute('SELECT asset,category FROM asset_categories WHERE asset IN ('+','.join('?' for _ in items)+')',list(categories)):
                    categories[row['asset']].append(row['category'])
            for item in items:item['snapshot']['categories']=categories[item['id']]
        return dict(items=items,
                    page=page, limit=limit, total=total)

    def save(self, data, aid=None, expected=None, objects=(), key=None, fixed_receipt=False):
        """Commit object metadata and one immutable version in the same transaction."""
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if key:
                done = db.execute("SELECT body FROM operations WHERE key=? AND state='done'", (key,)).fetchone()
                if done:
                    receipt=json.loads(done[0])
                    if fixed_receipt and not receipt.get('version'):
                        raise ValueError('素材包导入回执缺少固定版本，未改用当前版本')
                    return self.get(receipt['asset'],receipt.get('version') if fixed_receipt else None)
            old = db.execute('SELECT * FROM assets WHERE id=?', (aid,)).fetchone() if aid else None
            if aid and (not old or old['revision'] != expected):
                raise Conflict('资产已更新，请重新载入后保存；草稿仍保留')
            aid = aid or uid()
            snapshot = copy.deepcopy(data)
            name = str(snapshot.get('name', '')).strip()[:160]
            if not name:
                raise ValueError('请填写资产名称')
            snapshot['name'] = name
            for field in ('record_prompt', 'description'):
                snapshot[field] = str(snapshot.get(field, ''))[:200000]
            cats = list(dict.fromkeys(snapshot.get('categories', [])))
            tags = list(dict.fromkeys(str(x).strip()[:100] for x in snapshot.get('tags', []) if str(x).strip()))[:100]
            for cat in cats:
                if not db.execute('SELECT 1 FROM categories WHERE id=?', (cat,)).fetchone():
                    raise ValueError('分类不存在')
            for obj in objects:
                db.execute('INSERT OR IGNORE INTO objects VALUES(?,?,?,?)', (obj['hash'], obj['path'], obj['bytes'], encode(obj['meta'])))
            media = snapshot.get('media', [])
            if not media or len(media) > 100:
                raise ValueError('资产需要1～100项媒体')
            for item in media:
                if not db.execute('SELECT 1 FROM objects WHERE hash=?', (item['hash'],)).fetchone():
                    raise ValueError('媒体尚未完成入库')
            primary = next((x for x in media if x.get('role') == 'primary'), media[0])
            metadata = json.loads(db.execute('SELECT meta FROM objects WHERE hash=?', (primary['hash'],)).fetchone()[0])
            self._validate_bindings(db, aid, snapshot.get('bindings', []))
            version, now = uid(), time.time()
            snapshot.update(id=version, asset_id=aid, categories=cats, tags=tags, created=now)
            db.execute('INSERT INTO versions VALUES(?,?,?,?)', (version, aid, now, encode(snapshot)))
            favorite = int(bool(snapshot.get('favorite', False)))
            state = snapshot.get('state', 'candidate')
            if state not in ('candidate', 'selected'):
                raise ValueError('选用状态不支持')
            try:
                from fractions import Fraction
                fps = float(Fraction(metadata.get('fps') or '0')) or None
            except (ValueError, ZeroDivisionError):
                fps = None
            values = (name, version, metadata['kind'], favorite, state, now, snapshot.get('provenance', {}).get('type', 'local'),
                      metadata.get('width'), metadata.get('height'), metadata.get('duration'), fps, metadata.get('has_audio'))
            if old:
                db.execute('UPDATE assets SET name=?,version=?,kind=?,favorite=?,state=?,updated=?,source=?,width=?,height=?,duration=?,fps=?,has_audio=?,revision=revision+1 WHERE id=?', values + (aid,))
            else:
                db.execute('INSERT INTO assets(name,version,kind,favorite,state,updated,source,width,height,duration,fps,has_audio,id,revision,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)', values + (aid, now))
            db.execute('DELETE FROM asset_categories WHERE asset=?', (aid,))
            db.execute('DELETE FROM tags WHERE asset=?', (aid,))
            db.executemany('INSERT INTO asset_categories VALUES(?,?)', [(aid, x) for x in cats])
            db.executemany('INSERT INTO tags VALUES(?,?)', [(aid, x) for x in tags])
            if key:
                receipt=dict(asset=aid)
                if fixed_receipt:receipt['version']=version
                db.execute('INSERT OR REPLACE INTO operations VALUES(?,?,?,?,?)', (key, 'import', 'done', encode(receipt), now))
        return self.get(aid)

    def _validate_bindings(self, db, owner, bindings):
        if not isinstance(bindings, list) or len(bindings) > 32:
            raise ValueError('每个资产最多32项绑定')
        seen = set()

        def visit(aid, version, path, depth):
            if aid == owner or aid in path:
                raise ValueError('不允许自绑定或循环绑定')
            if depth > 8 or len(seen) > 128:
                raise ValueError('绑定超过8层或128项，请精简绑定包')
            row = db.execute('SELECT body FROM versions WHERE asset=? AND id=?', (aid, version)).fetchone()
            if not row:
                raise ValueError('绑定资产版本不存在')
            seen.add((aid, version))
            for child in json.loads(row[0]).get('bindings', []):
                visit(child['asset'], child['version'], path | {aid}, depth + 1)

        for item in bindings:
            if item.get('purpose') not in ('character', 'voice', 'scene', 'prop', 'costume', 'palette', 'accessory', 'control', 'texture'):
                raise ValueError('绑定用途不支持')
            if not isinstance(item.get('default', True), bool):
                raise ValueError('默认带入必须为开关')
            visit(item['asset'], item['version'], set(), 1)

    def trash(self, aid, revision, restore=False):
        with self.lock, self.connect() as db:
            result = db.execute('UPDATE assets SET deleted=?,revision=revision+1,updated=? WHERE id=? AND revision=?',
                                (None if restore else time.time(), time.time(), aid, revision))
            if result.rowcount != 1:
                raise Conflict('资产已发生变化，请刷新后重试')
        return self.get(aid)

    def catalog(self):
        with self.connect() as db:
            return dict(categories=[dict(r) for r in db.execute('SELECT * FROM categories ORDER BY system DESC,rowid')],
                        collections=[dict(r) for r in db.execute('SELECT * FROM collections ORDER BY name')],
                        tags=[r[0] for r in db.execute('SELECT DISTINCT tag FROM tags ORDER BY tag LIMIT 1000')], schema_version=SCHEMA_VERSION)

    def category(self, name, cid=None, move_to=None, delete=False):
        with self.lock, self.connect() as db:
            if delete:
                row = db.execute('SELECT * FROM categories WHERE id=?', (cid,)).fetchone()
                if not row or row['system']:
                    raise ValueError('系统分类不能删除')
                if db.execute('SELECT 1 FROM asset_categories WHERE category=?', (cid,)).fetchone():
                    if not move_to or move_to == cid or not db.execute('SELECT 1 FROM categories WHERE id=?', (move_to,)).fetchone():
                        raise ValueError('非空分类须选择迁移目标')
                    db.execute('INSERT OR IGNORE INTO asset_categories SELECT asset,? FROM asset_categories WHERE category=?', (move_to, cid))
                db.execute('UPDATE assets SET revision=revision+1,updated=? WHERE id IN(SELECT asset FROM asset_categories WHERE category=?)', (time.time(), cid))
                db.execute('DELETE FROM asset_categories WHERE category=?', (cid,))
                db.execute('DELETE FROM categories WHERE id=?', (cid,))
            elif cid:
                if not str(name).strip():
                    raise ValueError('名称不能为空')
                db.execute('UPDATE categories SET name=? WHERE id=?', (str(name).strip()[:80], cid))
            else:
                if not str(name).strip():
                    raise ValueError('名称不能为空')
                cid = uid()
                db.execute('INSERT INTO categories VALUES(?,?,0)', (cid, str(name).strip()[:80]))
        return self.catalog()

    def collection(self, name, description='', cid=None, revision=None, items=None):
        if not str(name).strip():
            raise ValueError('合集名称不能为空')
        with self.lock, self.connect() as db:
            if cid:
                if db.execute('UPDATE collections SET name=?,description=?,revision=revision+1 WHERE id=? AND revision=?',
                              (str(name)[:160], str(description)[:5000], cid, revision)).rowcount != 1:
                    raise Conflict('合集已更新，请刷新后重试')
            else:
                cid = uid()
                db.execute('INSERT INTO collections VALUES(?,?,?,1)', (cid, str(name)[:160], str(description)[:5000]))
            if items is not None:
                for aid in items:
                    if not db.execute('SELECT 1 FROM assets WHERE id=?', (aid,)).fetchone():
                        raise ValueError('合集成员不存在')
                db.execute('DELETE FROM collection_items WHERE collection=?', (cid,))
                db.executemany('INSERT INTO collection_items VALUES(?,?,?)', [(cid, aid, i) for i, aid in enumerate(dict.fromkeys(items))])
        return {**next(c for c in self.catalog()['collections'] if c['id'] == cid), 'items': self.collection_items(cid)}

    def collection_items(self, cid):
        with self.connect() as db:
            return [r[0] for r in db.execute('SELECT asset FROM collection_items WHERE collection=? ORDER BY position', (cid,))]
