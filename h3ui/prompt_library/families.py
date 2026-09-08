"""Evidence-backed model identities; helper components never select a family.

See docs/product/prompt-library-execution-plan.md §4.3 for author sources.
Additional mappings are metadata, not a model execution whitelist.
"""
from pathlib import PurePosixPath

H3_SOURCE='https://huggingface.co/Comfy-Org/MiniMax-H3'
KREA_SOURCE='https://huggingface.co/Comfy-Org/Krea-2'
KNOWN={}
for task in ('ref2va','fl2va'):
    for suffix in ('pruned_int8_convrot','pruned_bf16','pruned_fp8_scaled'):
        KNOWN[f'minimax_h3_{task}_{suffix}.safetensors']=('h3',H3_SOURCE)
KNOWN['minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors']=('h3','https://huggingface.co/smhfacct/Minimax-H3-fl2va-ref2va-hybrid-models')
for suffix in ('','_int8_convrot_v2'):
    KNOWN[f'FeiHou_MiniMax-H3_Remix_v0.6{suffix}.safetensors'.casefold()]=('h3','https://huggingface.co/FX-FeiHou/MiniMax-H3-Remix')
for variant in ('raw','turbo'):
    for precision in ('bf16','fp8_scaled','int8_convrot'):
        KNOWN[f'krea2_{variant}_{precision}.safetensors']=('krea2',KREA_SOURCE)


def identify(model, purpose, extra=()):
    name=PurePosixPath(str(model or '').replace('\\','/')).name.casefold()
    match=KNOWN.get(name)
    if match and ((purpose=='video' and match[0]=='h3') or (purpose=='image' and match[0]=='krea2')):
        return dict(family=match[0],evidence=match[1],model=str(model))
    for row in extra:
        if row.get('purpose')==purpose and str(row.get('model','')).replace('\\','/').casefold()==str(model).replace('\\','/').casefold() and row.get('family') and row.get('evidence'):
            return dict(family=row['family'],evidence=row['evidence'],model=str(model))
    return dict(family=None,evidence=None,model=str(model or ''))
