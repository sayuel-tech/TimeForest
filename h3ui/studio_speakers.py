"""Explicit target vocal order; never derive S identifiers from asset ordinals."""
import re

def speakers(seg, recipe):
    if recipe=='wenxi_av':return None  # Explicit compatibility recipe keeps its mapping.
    order=str(seg.get('speaker_order','')).strip()
    if order:
        ids=[s.strip() for s in re.split(r'[,，\s]+',order) if s.strip()]
        if any(not re.fullmatch('[1-9][0-9]?',s) for s in ids) or len(set(ids))!=len(ids):
            raise ValueError('发声顺序请填写不重复的角色ID，例如 2,1 表示角色2先说话')
        return {sid:i+1 for i,sid in enumerate(ids)}
    # An explicitly authored mapping is accepted without rewriting dialogue.
    found=re.findall(r'<Subject\s+(\d+)>\s*\(S(\d+)\)',seg.get('prompt','')+'\n'+seg.get('voice',''))
    mapping={}
    for sid,number in found:
        if sid in mapping and mapping[sid]!=int(number):raise ValueError('同一角色出现了不同的发声编号')
        mapping[sid]=int(number)
    if len(set(mapping.values()))!=len(mapping):raise ValueError('不同角色使用了同一个发声编号')
    return mapping
