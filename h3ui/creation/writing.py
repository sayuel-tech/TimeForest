"""Task snapshots, validated response artifacts, and explicit candidate application."""
import copy
import json
import time
from .contracts import ROOT, read, loads, validate, request_contract, digest
from .providers import Providers, ProviderError
from .service import uid
from ..studio_store import Conflict

TASK_LAYERS={'screenplay_draft':'screenplay','asset_analysis':'asset_bindings','asset_screenplay':'asset_screenplay',
             'storyboard':'storyboard','segment_plan':'segment','h3_prompt':'prompt',
             'image_observation':'visual_references','reference_image':'visual_references',
             'context_summary':'screenplay','change_impact':'screenplay'}
ACTIVE={'queued','running','submission_unknown'}


class Writing:
    def __init__(self,creation):
        self.creation=creation;self.store=creation.store;self.providers=Providers(creation)
        self.registry={r['contract_key']:r for r in read('配套清单/llm-task-registry.json')['tasks']}

    def context(self,pid,task,targets=None,instruction='',prompt_mode=None,layer=None,include_images=False):
        p=self.creation.get(pid,'authoring');layer=layer if task=='local_rewrite' and layer else TASK_LAYERS.get(task,'screenplay');targets=targets or []
        # Only the current scope and its writing basis; unrelated clip prompts are not a conversation.
        rows=[]
        relevant={'screenplay_draft':{'intent','screenplay'},'asset_analysis':{'screenplay','asset_bindings'},'asset_screenplay':{'screenplay','asset_bindings','asset_screenplay'}}.get(task)
        segment=next((s for s in (self.creation.layer(p,'segment') or {}).get('content',{}).get('segments',[]) if targets and s['ref']==targets[0]),None)
        for row in p['content']['layers']:
            if relevant and row['layer'] not in relevant:continue
            if targets:
                if row['layer']=='prompt' and row['target_ids']!=targets:continue
                if row['layer']=='storyboard':row=self.creation.layer(p,'storyboard',[segment['shot_ref']] if segment else targets)
                if row['layer']=='segment':
                    row=copy.deepcopy(row)
                    row['content']['segments']=[s for s in row['content'].get('segments',[]) if s['ref'] in targets or s['shot_ref'] in targets]
                if row['layer']=='visual_references':continue  # exact active inputs are exposed by the prompt input contract
            rows.append(row)
        materials=[dict(reference_key='layer:'+r['layer']+':'+','.join(r['target_ids']),kind='text',content=json.dumps(r['content'],ensure_ascii=False),media=None) for r in rows]
        from .conversations import materials as conversation_materials
        from .bindings import resolve
        materials.extend(conversation_materials(p,layer,targets))
        effective=resolve(self.creation,p,targets[0] if targets else None)
        materials.append(dict(reference_key='effective_bindings',kind='text',media=None,content=json.dumps(effective,ensure_ascii=False)))
        references=self.creation.references.materials(p)
        if targets:
            from .bindings import references as bound_references
            allowed={r['id'] for r in bound_references(p,effective)}
            references=[r for r in references if r['reference_key'] in allowed]

        materials.extend(references if include_images else [dict(r,kind='text',media=None) for r in references])
        if task=='h3_prompt' and len(targets)==1:
            preview=self.creation.movie.authoring_preview(pid,targets[0],False)
            materials.append(dict(reference_key='input_contract:'+targets[0],kind='text',content=json.dumps(preview['input_contract'],ensure_ascii=False),media=None))
        refs=[m['reference_key'] for m in materials]
        if task=='h3_prompt' and len(targets)==1:refs.extend(slot['reference_key'] for slot in preview['input_contract']['slots'])
        for r in p['content']['layers']:
            for key in ('shots','segments','blocks','needs'):
                refs.extend(x['ref'] for x in r['content'].get(key,[]))
        return dict(contract_version='tf-authoring/2.9',task_type=task,prompt_mode=prompt_mode,user_instruction=instruction,
                    allowed_refs=list(dict.fromkeys(refs)),allowed_write_fields=['payload'],target=dict(project_id=pid,layer=layer,target_ids=targets),
                    base_content_hash=self.creation.layer_hash(p,layer,targets),source_bundle_ids=[],materials=materials,
                    budget=dict(context_tokens=None,output_tokens=None,batch_id=None,batch_index=None))

    def preflight(self,data,validate_request=True):
        if validate_request:request_contract('LLMPreflight',data)
        c=copy.deepcopy(data['context']);target=c['target'];p=self.creation.get(target['project_id'],'authoring')
        key=c['task_type']+('.'+c['prompt_mode'] if c['task_type']=='h3_prompt' else '')
        spec=self.registry.get(key)
        if not spec:raise ValueError('任务合同不存在')
        if c['task_type']!='local_rewrite' and target['layer']!=TASK_LAYERS[c['task_type']]:raise ValueError('任务与写入范围不一致')
        if c['base_content_hash']!=self.creation.layer_hash(p,target['layer'],target['target_ids']):raise Conflict('请求依据已更新，请重新保存并准备')
        if target['layer']=='prompt' and len(target['target_ids'])!=1:raise ValueError('请选择要编写 Prompt 的片段')
        authoritative=self.context(p['id'],c['task_type'],target['target_ids'],'核对',c['prompt_mode'],target['layer'],True)
        known=set(authoritative['allowed_refs'])
        if set(c['allowed_refs'])-known:raise ValueError('请求引用不属于当前剧本')
        source={m['reference_key']:m for m in authoritative['materials']}
        for m in c['materials']:
            saved=source.get(m['reference_key'])
            if not saved:raise ValueError('请求材料没有已保存的来源')
            if m!=saved and not (saved['kind']=='image' and m==dict(saved,kind='text',media=None)):
                raise Conflict('请求材料与已保存版本不符')
        config=self.providers.get(data['provider_config_id']);self.providers.supported(config)
        if any(m['kind']=='image' for m in c['materials']):
            if config['vision']!='supported':raise ProviderError('VISION_UNCONFIRMED','当前服务未声明支持图片。请核实能力后配置，或明确取消附带图片，仅使用文字资料。')
        schema=read(spec['schema_file'])
        system=(ROOT/spec['common_template']).read_text(encoding='utf-8-sig')+'\n'+(ROOT/spec['task_template']).read_text(encoding='utf-8-sig')+'\n返回 JSON，严格遵循：\n'+json.dumps(schema,ensure_ascii=False)
        payload=dict(model=config['model_id'],messages=[dict(role='system',content=system),dict(role='user',content=json.dumps(c,ensure_ascii=False))],response_format={'type':'json_object'},max_tokens=c['budget']['output_tokens'] or config['max_output_tokens'] or 16384)
        images=self.creation.references.image_parts(p,c['materials'])
        if images:payload['messages'][1]['content']=[dict(type='text',text=json.dumps(c,ensure_ascii=False))]+images
        issues=[]
        if not config['enabled']:issues.append('请启用云端写作服务')
        if not config.get('credential_ref'):issues.append('请配置服务密钥')
        return dict(preflight_id=uid(),input_hash=digest([c,config]),ready=not issues,issues=issues,inference_executed=False),config,c,spec,payload

    def find(self,key,collection):
        for p in self.store.list()+self.store.list(trash=True):
            if p.get('mode') not in ('authoring','movie'):continue
            found=next((x for x in p.get(collection,[]) if x.get('job_id' if collection=='creation_jobs' else 'candidate_id')==key),None)
            if found:return p,found
        raise KeyError('记录不存在')

    def update_job(self,pid,jid,**values):
        def change(p):
            j=next(j for j in p['creation_jobs'] if j['job_id']==jid)
            j.update(values);j['event_seq']+=1;j['updated']=time.time()
        return self.store.mutate(pid,change)

    def start(self,data):
        request_contract('CreateLLMJob',data)
        c=data['context'];pid=c['target']['project_id']
        with self.store.lock:
            p=self.creation.get(pid,'authoring')
            previous=next((j for j in p['creation_jobs'] if j.get('request_key')==data['request_key']),None)
            if previous:
                if previous['request_hash']!=digest(data):raise Conflict('请求标识已用于不同 AI 任务')
                return previous
            if p['revision']!=data['source_revision']:raise Conflict('剧本已更新，请重新准备请求')
            pf,config,c,spec,payload=self.preflight(data,False)
            if not pf['ready']:raise ValueError('；'.join(pf['issues']))
            if any(j['state'] in ACTIVE for j in p['creation_jobs']):raise Conflict('当前剧本已有运行或待确认请求')
            jid=uid();job=dict(job_id=jid,kind='authoring',project_id=pid,state='queued',phase='等待写作',event_seq=1,candidate_ids=[],provider_request_id=None,failure_code=None,result_ref=None,inference_executed=False,
                 request_key=data['request_key'],request_hash=digest(data),context=c,config=copy.deepcopy(config),created=time.time(),updated=time.time(),error=None)
            p['creation_jobs'].append(job);p['content']['job_ids'].append(jid);self.store.save(p,p['revision'])
        started=self.creation.st.jobs.start('authoring_write',pid,lambda:self.execute(pid,jid,config,c,spec,payload),lane='cloud')
        if not started:self.update_job(pid,jid,state='failed',phase='通道忙碌',failure_code='CHANNEL_BUSY',error='当前通道忙碌，请稍后重新请求')
        return self.find(jid,'creation_jobs')[1]

    def execute(self,pid,jid,config,context,spec,payload):
        artifact=None
        try:
            if self.find(jid,'creation_jobs')[1]['state']=='cancelled':return
            self.update_job(pid,jid,state='running',phase='正在创作')
            result=self.providers.send(config,payload)
            message=result.get('choices',[{}])[0];text=message.get('message',{}).get('content');finish=message.get('finish_reason')
            artifact=dict(response_artifact_id=uid(),job_id=jid,contract_key=spec['contract_key'],response_hash=digest(text),raw_final_text=text if isinstance(text,str) else '',finish_reason=str(finish),validation_status='invalid_structure',repair_eligible=False,inference_executed=True)
            if finish!='stop':artifact['validation_status']='truncated';raise ProviderError('RESPONSE_TRUNCATED','响应没有完整结束，请缩小范围或调整输出预算；未自动修复。')
            if not isinstance(text,str) or not text.strip():raise ValueError('模型未返回可用正文')
            response=loads(text);validate(response,read(spec['schema_file']))
            self.validate_refs(response,context)
            artifact['validation_status']='valid'
            candidate=dict(candidate_id=uid(),job_id=jid,contract_key=spec['contract_key'],status=response['status'],payload=response['payload'],notes=response['notes'],issues=response['issues'],questions=response['questions'],applicable=response['status']=='ok',disposition='pending',base_content_hash=context['base_content_hash'])
            with self.store.lock:
                p=self.creation.get(pid);j=next(j for j in p['creation_jobs'] if j['job_id']==jid)
                p['artifacts'][artifact['response_artifact_id']]=artifact
                if j['state']=='cancelled':candidate.update(applicable=False,disposition='discarded')
                p['candidates'].append(candidate);j.update(state='cancelled' if j['state']=='cancelled' else 'succeeded',phase='候选已返回',candidate_ids=[candidate['candidate_id']],result_ref=dict(kind='response_artifact',id=artifact['response_artifact_id']),inference_executed=True,event_seq=j['event_seq']+1,updated=time.time());self.store.save(p,p['revision'])
        except Exception as exc:
            if artifact:
                artifact['repair_eligible']=bool(artifact['raw_final_text']) and artifact['finish_reason']=='stop'
                self.store.mutate(pid,lambda p:p['artifacts'].update({artifact['response_artifact_id']:artifact}))
            state='cancelled' if self.find(jid,'creation_jobs')[1]['state']=='cancelled' else 'submission_unknown' if getattr(exc,'code',None)=='SUBMISSION_UNKNOWN' else 'failed'
            self.update_job(pid,jid,state=state,phase='请求未完成',failure_code=getattr(exc,'code','INVALID_RESPONSE'),error=str(exc),result_ref=dict(kind='response_artifact',id=artifact['response_artifact_id']) if artifact else None,inference_executed=bool(artifact))

    def validate_refs(self,response,context):
        allowed=set(context['allowed_refs'])
        payload=response.get('payload') or {}
        # New objects in a single result can refer to one another; they are all
        # remapped together on apply, never treated as pre-existing project IDs.
        local={r['ref'] for name in ('blocks','shots','segments','needs') for r in payload.get(name,[])}
        def visit(x):
            if isinstance(x,dict):
                for k,v in x.items():
                    if k in ('source_refs','used_reference_keys','suggested_asset_refs','basis_refs','refs') and isinstance(v,list) and set(v)-allowed:raise ValueError('响应引用超出本次允许范围')
                    if k in ('shot_ref','upstream_ref','reference_key','target_ref') and isinstance(v,str) and v not in allowed|local:raise ValueError('响应目标超出本次允许范围')
                    visit(v)
            elif isinstance(x,list):
                for item in x:visit(item)
        visit(response)

    def apply(self,pid,data):
        request_contract('ApplyCandidate',data)
        def change(p):
            candidate=next((x for x in p['candidates'] if x['candidate_id']==data['candidate_id']),None)
            if not candidate or not candidate['applicable'] or candidate['disposition']!='pending':raise ValueError('候选不可应用')
            job=next(x for x in p['creation_jobs'] if x['job_id']==candidate['job_id']);context=job['context'];target=context['target']
            if data['base_content_hash']!=candidate['base_content_hash'] or self.creation.layer_hash(p,target['layer'],target['target_ids'])!=candidate['base_content_hash']:raise Conflict('候选返回后正文已修改，未覆盖新稿')
            current=self.context(pid,context['task_type'],target['target_ids'],'',context.get('prompt_mode'),target['layer'],True)
            available={m['reference_key']:m for m in current['materials']}
            for material in context['materials']:
                if material['reference_key'].startswith(('round:','basis:')):continue  # immutable saved responses, not mutable prose
                actual=available.get(material['reference_key'])
                if actual!=material and not(actual and actual['kind']=='image' and material==dict(actual,kind='text',media=None)):
                    raise Conflict('候选依据的故事或资产已修改，请保留候选并重新核对；未覆盖当前正文')
            payload=copy.deepcopy(data['edited_payload'] if data['edited_payload'] is not None else candidate['payload'])
            response={k:candidate[k] for k in ('status','notes','issues','questions')};response.update(payload=payload,contract_version='tf-authoring/2.9',task_type=context['task_type'])
            validate(response,read(self.registry[candidate['contract_key']]['schema_file']));self.validate_refs(response,context)
            if context['task_type'] in ('context_summary','change_impact','image_observation','reference_image'):
                p.setdefault('creation_notes',[]).append(dict(id=uid(),task_type=context['task_type'],target=target,base_content_hash=context['base_content_hash'],payload=payload,candidate_id=candidate['candidate_id']))
                candidate['disposition']='applied';return [candidate['candidate_id']],{}
            if context['task_type']=='h3_prompt':
                previous=(self.creation.layer(p,'prompt',target['target_ids']) or {}).get('content',{})
                payload=dict({k:previous[k] for k in ('profile_id','input_contract_id') if k in previous},prompt_mode=context['prompt_mode'],payload=payload)
            if context['task_type']=='local_rewrite':
                from .service import COLLECTIONS
                if len(target['target_ids'])!=1 or target['layer'] not in COLLECTIONS:raise ValueError('局部改写须指定一段正文、分镜或片段')
                original=self.creation.layer(p,target['layer'],target['target_ids'])
                collection=COLLECTIONS[target['layer']]
                if not original or len(original['content'].get(collection,[]))!=1:raise Conflict('局部改写目标已变化')
                text=payload['replacement_text'];payload=copy.deepcopy(original['content']);payload[collection][0]['text']=text
            remap={}
            for collection in ('blocks','shots','segments','needs'):
                for item in payload.get(collection,[]):
                    if item['ref'] not in context['allowed_refs']:remap[item['ref']]='tmp:'+candidate['candidate_id']+':'+item['ref']
            payload=self.creation.remap(payload,remap)
            if context['task_type']=='segment_plan' and target['target_ids']:
                if any(item['shot_ref']!=target['target_ids'][0] for item in payload.get('segments',[])):raise ValueError('切分结果超出当前分镜')
                target=dict(target,target_ids=[])
            existing=self.creation.layer(p,target['layer'],target['target_ids'])
            result=self.creation.write_layer(p,dict(layer=target['layer'],target_ids=target['target_ids'],base_content_hash=existing['content_hash'] if existing else None,content=payload,update_mode='merge_targets' if target['target_ids'] and target['layer']!='prompt' or context['task_type'] in ('asset_analysis','segment_plan') else 'replace_scope',removed_target_ids=[]))
            candidate['disposition']='applied';return result
        return self.creation.mutate(pid,data,change)

    def cancel(self,jid):
        p,job=self.find(jid,'creation_jobs')
        if job['state'] not in ACTIVE:return job
        self.update_job(p['id'],jid,state='cancelled',phase='已取消接收；服务已开始的请求可能仍计费')
        return self.find(jid,'creation_jobs')[1]

    def repair(self,data):
        request_contract('RepairCandidate',data)
        with self.store.lock:
            p,original=self.find(data['job_id'],'creation_jobs')
            previous=next((j for j in p['creation_jobs'] if j.get('request_key')==data['request_key']),None)
            if previous:
                if previous['request_hash']!=digest(data):raise Conflict('请求标识已用于其他任务')
                return previous
            artifact=p['artifacts'].get(data['response_artifact_id'])
            if not artifact or artifact['job_id']!=original['job_id'] or data['repair_of']!=original['job_id']:raise ValueError('修复来源不属于原任务')
            if artifact['response_hash']!=data['source_response_hash']:raise Conflict('原响应已变化')
            if not artifact['repair_eligible'] or artifact['finish_reason']!='stop':raise ValueError('截断或缺失的响应不能通过格式修复补写')
            if original.get('repair_of'):raise ValueError('不递归修复；请重新整理原任务或手动编辑')
            if any(j['state'] in ACTIVE for j in p['creation_jobs']):raise Conflict('请先处理当前运行或待确认请求')
            context=copy.deepcopy(original['context']);config=self.providers.get(original['config']['config_id']);self.providers.supported(config)
            contract=context['task_type']+('.'+context['prompt_mode'] if context['task_type']=='h3_prompt' else '')
            spec=self.registry[contract]
            text=(ROOT/'运行模板/format_repair.txt').read_text(encoding='utf-8-sig')+'\n'+json.dumps(read(spec['schema_file']),ensure_ascii=False)
            payload=dict(model=config['model_id'],messages=[dict(role='system',content=text),dict(role='user',content=artifact['raw_final_text'])],response_format=dict(type='json_object'),max_tokens=config['max_output_tokens'] or 16384)
            jid=uid();job=dict(job_id=jid,kind='authoring',project_id=p['id'],state='queued',phase='等待格式修复',event_seq=1,candidate_ids=[],provider_request_id=None,failure_code=None,result_ref=None,inference_executed=False,request_key=data['request_key'],request_hash=digest(data),context=context,config=copy.deepcopy(config),created=time.time(),updated=time.time(),error=None,repair_of=original['job_id'],source_response_hash=artifact['response_hash'])
            p['creation_jobs'].append(job);p['content']['job_ids'].append(jid);self.store.save(p,p['revision'])
        if not self.creation.st.jobs.start('authoring_repair',p['id'],lambda:self.execute(p['id'],jid,config,context,spec,payload),lane='cloud'):
            self.update_job(p['id'],jid,state='failed',phase='通道忙碌',failure_code='CHANNEL_BUSY')
        return self.find(jid,'creation_jobs')[1]
