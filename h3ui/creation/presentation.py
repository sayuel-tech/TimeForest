"""Public execution DTOs; worker paths and credentials remain server-side."""
import copy
from .contracts import read,validate


def dto(name,value):
    schema=read('数据契约/api-responses.schema.json')['$defs'][name]
    result={key:copy.deepcopy(value[key]) for key in schema['properties'] if key in value}
    validate(result,schema);return result


def job(value):return dto('Job',value)


def prepared(value):return dto('PreparedGeneration',dict(value,submitted=False))


def snapshot(value):
    """Existing /projects presentation includes UI metadata, never execution paths."""
    value=copy.deepcopy(value)
    for row in value.get('movie_prepared',[]):
        row.pop('assets',None);row.pop('compiled',None);row.pop('context',None);row.pop('request_hash',None)
    for row in value.get('creation_jobs',[]):
        row.pop('request_hash',None)
        record=row.get('record')
        if record:
            for key in ('assets','compiled','context','request_hash'):record.pop(key,None)
            for part in record.get('parts',[]):part.pop('file',None)
    for row in value.get('movie_exports',[]):
        for part in row.get('manifest',{}).get('parts',[]):part.pop('file',None)
    return value
