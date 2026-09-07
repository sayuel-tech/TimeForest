"""Expand fixed versions into media responsibilities; documentary prose is excluded."""
import hashlib


def expand(library, asset_id, version=None, owner=None):
    root = library.store.get(asset_id, version)
    owner = owner or asset_id
    result = []

    def walk(item, purpose, path, selected, depth):
        if depth > 8 or len(result) >= 128:
            raise ValueError('绑定包过大，请减少绑定深度或数量')
        snap = item['snapshot']
        primary = next((m for m in snap['media'] if m.get('role') == 'primary'), snap['media'][0])
        media = [{**{k:v for k,v in m.items() if k in ('id','hash','role','name')}, 'meta': library.store.object(m['hash'])} for m in snap['media']]
        for m in media:
            m['meta'] = {k: v for k, v in m['meta'].items() if k not in ('path', 'generation_records')}
            m['url'] = '/api/v5/library/media/' + m['hash']
        key = hashlib.sha256((str(owner) + '/' + path).encode()).hexdigest()[:24]
        result.append(dict(key=key, asset=item['id'], version=snap['id'], name=snap['name'], media=media,
                           deleted=bool(item.get('deleted')),
                           selected_media=primary['id'], purpose=purpose, selected=selected, owner=owner,
                           categories=snap.get('categories', []), parent=path.rsplit('/', 1)[0] if '/' in path else None))
        for index, binding in enumerate(snap.get('bindings', [])):
            child = library.store.get(binding['asset'], binding['version'])
            walk(child, binding['purpose'], path + '/' + str(index), selected and binding.get('default', True), depth + 1)

    kind = library.store.object(root['snapshot']['media'][0]['hash'])['kind']
    category = next((x for x in root['snapshot']['categories'] if x in ['control', 'character', 'scene', 'prop', 'costume', 'voice', 'palette', 'accessory', 'texture']), None)
    walk(root, 'voice' if kind == 'audio' else category or 'character', asset_id, True, 0)
    return dict(asset=root['id'], version=root['snapshot']['id'], owner=owner, entries=result)
