"""Integer-frame planning for the studio. No model code is executed here."""
from decimal import Decimal, ROUND_HALF_UP
import math

FPS = 24

def frames(seconds):
    return int((Decimal(str(seconds)) * FPS).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def aligned(n):
    return 5 + 17 * max(0, math.ceil((int(n) - 5) / 17))

def story_plan(seconds, cap_seconds=15, boundaries=None):
    total = frames(seconds)
    if not 24 <= total <= 86400:
        raise ValueError('目标时长须为1～3600秒')
    cap = 5 + 17 * math.floor((min(frames(cap_seconds), 360) - 5) / 17)
    if cap < 124:
        raise ValueError('单次渲染上限至少为124帧（约5.167秒）')
    legal = list(range(124, cap + 1, 17))
    count = 1 if total <= cap else 1 + math.ceil((total - cap) / (cap - 22))
    boundaries = boundaries or {}
    result=[];remaining=total;cursor=0
    for i in range(count):
        prefix=0 if i==0 or boundaries.get(i)=='new_scene' else 22
        left=count-i-1
        if not left:
            raw=max(124,aligned(remaining+prefix))
            if raw>cap:raise ValueError('场景规划无法满足渲染上限')
            deliver=remaining
        else:
            future_prefix=[0 if boundaries.get(j)=='new_scene' else 22 for j in range(i+1,count)]
            max_future=sum(cap-c for c in future_prefix)
            min_future=sum(124-c for c in future_prefix[:-1])+1
            choices=[r for r in legal if min_future<=remaining-(r-prefix)<=max_future]
            if not choices:raise ValueError('片段边界无法生成合法时间线')
            raw=min(choices,key=lambda r:(abs((r-prefix)-remaining/(left+1)),r))
            deliver=raw-prefix
        result.append(dict(index=i,raw=raw,head=prefix,deliver=deliver,tail=raw-prefix-deliver,
                           start=cursor,duration=deliver/FPS,boundary='new_scene' if prefix==0 else 'continue'))
        remaining-=deliver;cursor+=deliver
    assert cursor==total and all(s['raw']<=345 and s['raw']%17==5 for s in result)
    assert all(s['tail']==0 for s in result[:-1])
    return result

def geometry(settings):
    if settings.get('size_mode')=='custom':
        w,h=int(settings['width']),int(settings['height'])
        if w%32 or h%32 or not 128<=w<=2048 or not 128<=h<=2048:
            raise ValueError('自定义宽高须为128～2048内的32倍数')
    else:
        ratios={'9:16':9/16,'16:9':16/9,'1:1':1,'4:3':4/3,'3:4':3/4}
        ratio=ratios.get(settings.get('aspect','9:16'))
        if ratio is None:raise ValueError('画面比例不支持')
        area=float(settings.get('megapixels',.3))*1e6
        if not .1e6<=area<=1.1e6:raise ValueError('一采面积须为0.1～1.1MP')
        w=max(128,round(math.sqrt(area*ratio)/32)*32)
        h=max(128,round(math.sqrt(area/ratio)/32)*32)
    scale=float(settings.get('scale',1.5)) if settings.get('two_pass') else 1
    if not 1<=scale<=2:raise ValueError('放大倍率须为1～2')
    return dict(width=w,height=h,output_width=round(w*scale/32)*32,
                output_height=round(h*scale/32)*32)
