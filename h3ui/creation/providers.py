"""Configurable Chat Completions adapter; reserved local providers remain disabled."""
import json
import os
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from .contracts import read, request_contract, digest, loads


class ProviderError(ValueError):
    def __init__(self,code,message): super().__init__(message);self.code=code


def endpoint(base,resource):
    url=urlsplit(base.strip())
    if url.scheme not in ('http','https') or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise ValueError('请填写有效的服务地址，不含凭据或查询参数')
    path=url.path.rstrip('/')
    for suffix in ('/chat/completions','/models'):
        if path.endswith(suffix):path=path[:-len(suffix)]
    return urlunsplit((url.scheme,url.netloc,path+'/'+resource,'',''))


class DeepSeekChat:
    def __init__(self,allowed=True):self.allowed=allowed

    def send(self,config,credential,payload=None,resource='chat/completions'):
        if not self.allowed:raise ProviderError('EXECUTION_FORBIDDEN','此隔离环境禁止真实模型或账户请求')
        request=Request(endpoint(config['base_url'],resource),data=json.dumps(payload,ensure_ascii=False).encode() if payload else None,
                        headers={'Authorization':'Bearer '+credential,'Content-Type':'application/json'},method='POST' if payload else 'GET')
        try:
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self,*args,**kwargs):return None
            with build_opener(NoRedirect()).open(request,timeout=180) as response:
                raw=response.read(8*1024*1024+1)
                if len(raw)>8*1024*1024:raise ProviderError('RESPONSE_TOO_LARGE','模型响应过大；请缩小写作范围')
                return loads(raw.decode())
        except HTTPError as exc:
            code='MODEL_UNAVAILABLE' if exc.code in (400,404,410) else 'PROVIDER_REJECTED'
            raise ProviderError(code,f'写作服务返回 HTTP {exc.code}。请核对地址、模型与账户配置；当前草稿和候选保留。') from None
        except (URLError,TimeoutError):
            raise ProviderError('SUBMISSION_UNKNOWN','连接中断，无法确认服务是否已经执行；未自动重发。') from None


class Providers:
    def __init__(self,creation):
        self.creation=creation;self.store=creation.store
        self.transport=DeepSeekChat(not creation.st.ctx['cfg'].get('studio_disable_generation',False))

    def list(self):
        saved=self.store.get_default('authoring_providers')
        return saved if saved is not None else read('配置样例/llm-providers.example.json')

    def get(self,id):
        config=next((x for x in self.list() if x['config_id']==id),None)
        if config is None:raise ValueError('服务配置不存在')
        return config

    def supported(self,config):
        if config['provider_kind'] not in ('deepseek','openai_compatible') or config['api_style']!='chat':
            raise ProviderError('PROVIDER_NOT_IMPLEMENTED','请选择 DeepSeek 或兼容 Chat Completions 的云端服务；其他接口尚未接入。')

    def save(self,data):
        request_contract('SaveProvider',data);config=dict(data['config']);endpoint(config['base_url'],'models')
        with self.store.lock:
            rows=self.list();previous=next((c for c in rows if c['config_id']==config['config_id']),None)
            config['credential_ref']=previous.get('credential_ref') if previous else None
            if config['provider_kind'] not in ('deepseek','openai_compatible') or config['api_style']!='chat':config['enabled']=False
            if config['enabled']:
                allowed=('json_object','prompt_json') if config['provider_kind']=='openai_compatible' else ('json_object',)
                if config['structured_mode'] not in allowed:raise ValueError('当前接口不支持所选 JSON 返回方式')
                if not config.get('model_id'):raise ValueError('请填写模型 ID')
            rows=[c for c in rows if c['config_id']!=config['config_id']]+[config]
            self.store.set_default('authoring_providers',rows)
        return config

    def secret_path(self,config_id):
        return self.store.root/'credentials'/(digest(config_id)+'.key')

    def credential(self,data,remove=False):
        request_contract('DeleteCredential' if remove else 'WriteCredential',data)
        with self.store.lock:
            rows=self.list();config=next((c for c in rows if c['config_id']==data['config_id']),None)
            if not config:raise ValueError('服务配置不存在')
            path=self.secret_path(config['config_id'])
            if remove:
                if data['credential_ref']!=config.get('credential_ref'):raise ValueError('凭据标识已变化')
                path.unlink(missing_ok=True);config['credential_ref']=None
            else:
                if len(data['secret'])>8192:raise ValueError('凭据长度不合法')
                path.parent.mkdir(parents=True,exist_ok=True)
                tmp=path.with_suffix('.tmp');tmp.write_text(data['secret'],encoding='utf-8');os.chmod(tmp,0o600);tmp.replace(path)
                config['credential_ref']='credential:'+digest(config['config_id'])
            self.store.set_default('authoring_providers',rows)
        return dict(config_id=config['config_id'],credential_ref=config['credential_ref'],configured=not remove,masked_hint='已配置' if not remove else '未配置')

    def send(self,config,payload=None,resource='chat/completions'):
        self.supported(config)
        if not config['enabled']:raise ProviderError('PROVIDER_DISABLED','请先配置并启用云端写作服务')
        if isinstance(self.transport,DeepSeekChat) and not self.transport.allowed:
            raise ProviderError('EXECUTION_FORBIDDEN','此隔离环境禁止真实模型或账户请求')
        path=self.secret_path(config['config_id'])
        if not config.get('credential_ref') or not path.is_file():raise ProviderError('CREDENTIAL_MISSING','请先在写作设置中保存服务密钥')
        return self.transport.send(config,path.read_text(encoding='utf-8'),payload,resource)
