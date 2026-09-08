"""Authoring warnings using the existing input and vocal-order contracts."""
import re
from ..studio_inputs import validate_tags
from ..studio_speakers import speakers


def warnings(text, rows, segment=None, recipe=None):
    result=[]
    try: validate_tags(text,rows)
    except ValueError as exc: result.append(str(exc))
    subjects={str(r.get('subject')) for r in rows if r.get('subject')}
    mentioned=set(re.findall(r'<Subject\s+(\d+)>',text))
    if mentioned-subjects:
        result.append('以下角色ID未在当前素材职责中登记：'+', '.join(sorted(mentioned-subjects))+'。若正文自行定义角色，请人工核对。')
    try:
        mapping=speakers(segment or dict(prompt=text),recipe)
        numbers=set(re.findall(r'\bS(\d+)\b',text))
        if mapping is not None and numbers-{str(n) for n in mapping.values()}:
            result.append('正文发声编号未全部包含在当前发声顺序/显式角色映射中；S编号不同于素材编号。')
    except ValueError as exc: result.append(str(exc))
    return result
