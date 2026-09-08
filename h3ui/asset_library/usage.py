"""Idempotent historical use registration after a project has committed."""
import time
from .store import encode


class UsageRegistrationPending(RuntimeError):
    """The project is committed; only the library-side completion needs retry."""


def complete(library, project, entries, operation, used_at=None):
    try:
        library.record_usage(project, entries, operation, used_at)
    except Exception as error:
        raise UsageRegistrationPending('项目内容已保存，但资产使用登记未完成。图片项目请再次保存；视频接续请刷新项目后保存重试登记，请勿重复导入素材。') from error


def record(library, project, entries, operation, used_at=None):
    if not entries:
        return
    key='library-usage:'+operation
    when=time.time() if used_at is None else used_at
    with library.store.lock, library.store.connect() as db:
        if db.execute('SELECT 1 FROM operations WHERE key=?', (key,)).fetchone():
            return
        for entry in entries:
            ref=entry['reference']
            # These are server-owned committed references, never client paths.
            item=library.store.get(ref['asset'],ref['version'])
            if not any(m['id']==ref['media'] and m['hash']==ref['hash'] for m in item['snapshot']['media']):
                raise ValueError('资产使用登记的固定版本媒体不匹配')
            db.execute('INSERT OR REPLACE INTO refs VALUES(?,?,?,?,?)',
                       (project+':'+entry['id'],ref['asset'],ref['version'],project,encode(ref)))
            db.execute('UPDATE assets SET used=MAX(COALESCE(used,0),?) WHERE id=?',(when,ref['asset']))
        db.execute('INSERT INTO operations VALUES(?,?,?,?,?)',(key,'library_usage','done',encode({'project':project}),when))
