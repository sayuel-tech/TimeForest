"""Offline validation of the bundled contract vocabulary; no remote references."""
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).parent / 'resources'


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('返回 JSON 含重复字段：' + key)
        result[key] = value
    return result


def loads(text):
    return json.loads(text, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('非法数值：' + value)))


def read(name):
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('配套资源路径无效')
    return loads(path.read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate(value, schema, root=None, path='$'):
    """Validate the local schema subset used by the shipped contracts.

    This is not an extensible JSON Schema engine: unsupported assertion keywords
    fail closed, and no URL or external schema is ever resolved.
    """
    root = schema if root is None else root
    if isinstance(schema, bool):
        if not schema: raise ValueError(path + '：不允许此字段')
        return
    supported = {'$schema','$defs','$ref','title','description','default','examples','writeOnly',
                 'type','const','enum','oneOf','anyOf','allOf','properties','required',
                 'additionalProperties','minProperties','items','minItems','maxItems',
                 'uniqueItems','minLength','maxLength','pattern','minimum','maximum',
                 'exclusiveMinimum','exclusiveMaximum','if','then','else'}
    if set(schema) - supported:
        raise ValueError('尚未支持的合同约束：' + ','.join(set(schema)-supported))
    if 'if' in schema:
        try: validate(value,schema['if'],root,path); branch='then'
        except ValueError: branch='else'
        if branch in schema: validate(value,schema[branch],root,path)
    if '$ref' in schema:
        ref = schema['$ref']
        if not ref.startswith('#/'): raise ValueError('禁止外部合同引用')
        target = root
        for part in ref[2:].split('/'): target = target[part.replace('~1','/').replace('~0','~')]
        validate(value, target, root, path)
    for kind in ('oneOf','anyOf','allOf'):
        if kind not in schema: continue
        matches = 0
        for option in schema[kind]:
            try: validate(value, option, root, path); matches += 1
            except ValueError: pass
        if (kind == 'oneOf' and matches != 1) or (kind == 'anyOf' and not matches) or (kind == 'allOf' and matches != len(schema[kind])):
            raise ValueError(path + '：内容不符合所选合同')
    types = {'object': isinstance(value,dict), 'array': isinstance(value,list),
             'string': isinstance(value,str), 'integer': type(value) is int,
             'number': type(value) in (int,float) and math.isfinite(value),
             'boolean': type(value) is bool, 'null': value is None}
    if 'type' in schema and not types.get(schema['type'],False): raise ValueError(path + '：字段类型不正确')
    if 'const' in schema and value != schema['const']: raise ValueError(path + '：固定值不正确')
    if 'enum' in schema and value not in schema['enum']: raise ValueError(path + '：选项不支持')
    if isinstance(value,dict):
        if set(schema.get('required',[]))-set(value): raise ValueError(path + '：缺少必要字段')
        if len(value)<schema.get('minProperties',0): raise ValueError(path + '：缺少内容')
        for key,item in value.items():
            definition=schema.get('properties',{}).get(key,schema.get('additionalProperties',True))
            validate(item,definition,root,path+'.'+key)
    elif isinstance(value,list):
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',math.inf): raise ValueError(path+'：数量超出范围')
        if schema.get('uniqueItems') and len({json.dumps(x,sort_keys=True) for x in value})!=len(value): raise ValueError(path+'：存在重复项')
        for index,item in enumerate(value): validate(item,schema.get('items',True),root,f'{path}[{index}]')
    elif isinstance(value,str):
        if not schema.get('minLength',0)<=len(value)<=schema.get('maxLength',math.inf): raise ValueError(path+'：文字长度超出范围')
        if 'pattern' in schema and not re.search(schema['pattern'],value): raise ValueError(path+'：文字格式不正确')
    elif type(value) in (int,float):
        if not math.isfinite(value): raise ValueError(path+'：数值无效')
        for key,valid in [('minimum',lambda n:value>=n),('maximum',lambda n:value<=n),('exclusiveMinimum',lambda n:value>n),('exclusiveMaximum',lambda n:value<n)]:
            if key in schema and not valid(schema[key]): raise ValueError(path+'：数值超出范围')


def request_contract(name, value):
    schema=read('数据契约/api-requests.schema.json')
    validate(value,schema['$defs'][name],schema)
