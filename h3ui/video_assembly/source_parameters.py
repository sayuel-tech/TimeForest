"""Assembly fixed-source adapter; display parsing belongs to the asset library."""
import copy
from ..asset_library.generation_records import parameter_records


def from_library(library, reference):
    """Only the referenced media/version, never a latest-version fallback."""
    if not isinstance(reference,dict) or reference.get('type')!='library': return []
    if any(not isinstance(reference.get(k),str) or not reference[k] for k in ('asset','version','media','hash')):return []
    try:
        item=library.store.get(reference['asset'],reference['version'])
        media=next((m for m in item['snapshot']['media'] if m['id']==reference['media']),None)
        if not media or media.get('hash')!=reference.get('hash'): return []
        # Legacy asset-wide provenance is only unambiguous for a single medium.
        origin=media.get('provenance')
        if origin is None and len(item['snapshot']['media'])==1:origin=item['snapshot'].get('provenance')
        return parameter_records(origin)
    except (KeyError,ValueError):
        return []


def for_clip(library, clip):
    if 'source_parameters' in clip:
        return copy.deepcopy(clip['source_parameters'])
    return from_library(library,clip.get('provenance'))
