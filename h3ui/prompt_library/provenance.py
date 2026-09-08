"""Optional authoring provenance is never an instruction to the generator."""
def sources(value):
    if value is None: return {}
    if not isinstance(value,dict) or len(value)>12: raise ValueError('提示词来源标记无效')
    result={}
    for key,row in value.items():
        if key not in ('prompt','custom','staging','beats','ending','voice','soundscape','music','speaker_order','swap_custom_prompt'):raise ValueError('提示词来源字段无效')
        if not isinstance(row,dict) or not isinstance(row.get('text'),str) or len(row['text'])>500000:raise ValueError('提示词来源标记无效')
        if isinstance(row.get('record'),dict):
            fields=('project','project_name','mode','run','candidate','segment','task','output','asset','asset_version','media','external','model','family','evidence')
            record={k:v for k,v in row['record'].items() if k in fields and isinstance(v,(str,int,bool))}
            if any(isinstance(v,str) and len(v)>2000 for v in record.values()):raise ValueError('制作记录来源过长')
            result[key]=dict(record=record,text=row['text'])
        else:
            if not isinstance(row.get('entry'),str) or len(row['entry'])>80 or not isinstance(row.get('version'),int) or row['version']<1:raise ValueError('提示词来源标记无效')
            result[key]={k:row[k] for k in ('entry','version','text')}
    return result
