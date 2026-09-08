"""Read saved run configuration, never defaults/current project settings/graphs.

The selected fixed-version media owns the provenance, not the asset's cover.
Return display-only known fields; do not leak file paths or raw plugin payloads.
"""
from ..studio_recipes import PARAMETERS, RECIPES
from ..studio_capabilities import decorate_catalog

_FIELDS = [dict(key=k,label=l,type=t,group=g,help=h) for k,l,t,g,h in PARAMETERS]
_RECIPES = {r['id']:r for r in decorate_catalog(dict(parameters=_FIELDS,
    recipes=[dict(id=k,**r) for k,r in RECIPES.items()]), {})['recipes']}


def parameter_records(origin):
    records = []
    if not isinstance(origin, dict):
        return records
    for _ in range(16):
        if origin.get('type')!='portable_pack':break
        origin=origin.get('records')
        if not isinstance(origin,dict):return records
    if origin.get('type')=='portable_pack':return records

    def add(settings, title, seed=None, segment=None):
        if not isinstance(settings, dict):
            return
        fields = []
        recipe=_RECIPES.get(settings.get('recipe'),{})
        for field in recipe.get('parameters',_FIELDS):
            key,label,group=field['key'],field['label'],field['group']
            if any(k in settings and settings[k]!=v for k,v in field.get('when',{}).items()):continue
            value = settings.get(key)
            if value is None or not isinstance(value, (str, int, float, bool)):
                continue
            if key == 'recipe': value = RECIPES.get(value, {}).get('name', value)
            fields.append(dict(key=key, label=label, group=group, value=value))
        slots=settings.get('loras',[]) if isinstance(settings.get('loras'),list) and not recipe.get('official') else []
        for i, slot in enumerate(slots):
            if not isinstance(slot, dict): continue
            for key, label in [('file','文件'),('strength','强度'),('bypass','跳过本槽')]:
                value = slot.get(key)
                if value is not None and isinstance(value, (str,int,float,bool)):
                    fields.append(dict(key=f'lora_{i}_{key}',label=f'LoRA {i+1} · {label}',group='lora',value=value))
        if fields:
            if seed is not None and isinstance(seed, (str,int)):
                fields.append(dict(key='actual_seed',label='本次实际种子',group='sampling',value=str(seed)))
            if isinstance(segment, dict):
                for key,label in [('seed_mode','种子模式'),('seconds','希望新增时长（秒）'),('sound','续接声音')]:
                    value=segment.get(key)
                    if value is not None and isinstance(value,(str,int,float,bool)):
                        fields.append(dict(key=key,label=label,group='assets' if key=='sound' else 'sampling',value=value))
            records.append(dict(title=title,fields=fields))

    def walk(node, title, seed=None, depth=0):
        if not isinstance(node,dict) or depth>12: return
        if node.get('type')=='portable_pack':
            walk(node.get('records'),title,seed,depth+1);return
        snapshot=node.get('snapshot')
        if isinstance(snapshot,dict):
            extension=snapshot.get('extension')
            if isinstance(extension,dict):
                configurations=extension.get('configurations',{})
                if isinstance(configurations,dict):
                    add(configurations.get(extension.get('recipe')),title,node.get('seed',seed),extension)
            # A concat-only snapshot has no single generation configuration.
        manifest=node.get('manifest')
        if isinstance(manifest,dict):
            segment=manifest.get('segment',{})
            actual=segment.get('actual_seed') if isinstance(segment,dict) else None
            add(manifest.get('settings'),title,actual if actual is not None else seed,segment)
        if isinstance(node.get('records'),dict):
            walk(node['records'],title,node.get('seed',seed),depth+1)
        for i,row in enumerate(node.get('selected_runs',[]) if isinstance(node.get('selected_runs'),list) else []):
            if isinstance(row,dict):walk(row.get('records'),f'{title} · 片段 {i+1}',row.get('seed'),depth+1)
        for i,task in enumerate(node.get('tasks',[]) if isinstance(node.get('tasks'),list) else []):
            if not isinstance(task,dict):continue
            for run in task.get('runs',[]) if isinstance(task.get('runs'),list) else []:
                if isinstance(run,dict) and run.get('id')==task.get('selected'):
                    walk(run.get('records'),f'{title} · 内部任务 {i+1}',run.get('seed'),depth+1)
    if origin.get('type') == 'generated_image':
        from ..image_studio.parameters import public_parameters
        saved = origin.get('records', {})
        snap = saved.get('snapshot', {}) if isinstance(saved, dict) else {}
        if isinstance(snap, dict):
            fields = []
            for field in public_parameters().get(snap.get('submode'), []):
                values = snap.get(field.get('scope', 'settings'), {})
                value = values.get(field['key']) if isinstance(values, dict) else None
                if field['key'] == 'seed': value = saved.get('seed')
                if isinstance(value, (str, int, float, bool)):
                    fields.append(dict(key=field['key'], label=field['label'], group=field['group'], value=value))
            if fields: records.append(dict(title='图片制作参数', kind='image', fields=fields))
        return records
    walk(origin,'原片段制作参数',origin.get('seed'))
    return records
