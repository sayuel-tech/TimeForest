"""Editable delivery order, separate from the immutable generation source chain.

Keys identify source clips or selected extension slots, never arbitrary files.
Legacy projects derive their original source/extension order without a write.
"""


def entries(project):
    runs = {r['id']: r for r in project['assembly']['runs']}
    rows = []
    for clip in project['assembly']['clips']:
        if clip.get('removed_at'):
            continue
        rows.append(('clip:' + clip['id'], clip, None))
        for extension in clip['extensions']:
            run = runs.get(extension.get('selected'))
            if (not extension.get('removed_at') and run and not run.get('removed_at')
                    and run['state'] == 'success' and run.get('extension') == extension['id']):
                rows.append(('extension:' + extension['id'], clip, run))
    return rows


def order(project):
    keys = [key for key, _, _ in entries(project)]
    stored = project['assembly'].get('track_order', [])
    # Removed/unselected slots disappear; newly available slots append once.
    return list(dict.fromkeys([key for key in stored if key in keys] + keys))


def validate(value, expected):
    if (not isinstance(value, list) or not all(isinstance(k, str) for k in value)
            or len(value) != len(set(value)) or set(value) != set(expected)):
        raise ValueError('视频轨道已变化或包含无效片段，请重新读取后排序；原草稿保留')
    return list(value)
