import {projectOriginLink} from '../../ui/asset-origin.js';
import {esc,opts,toast} from '../../ui/primitives.js';
import {chooseAction} from '../../ui/choice-dialog.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {promptApi,promptCatalog} from './api.js';
import {openEditor,editBranch,contentText} from './editor.js';

/** Shared library browser for the full page and in-workspace selection. */
export async function mountPromptBrowser(root,{signal,purpose='video',branch,onChoose}={}){
  let catalog=await promptCatalog(signal),selected=null,offset=0,serial=0,busy=false,globalSearch=false;
  let filters={purpose,branch:branch||'',q:'',kind:'',favorite:'',trash:''};
  const alive=()=>root.isConnected&&!signal?.aborted;
  root.innerHTML=`<div class="prompt-library-browser"><aside data-tree></aside><section><div class="row prompt-filters"><input data-search aria-label="搜索提示词" placeholder="搜索名称、正文或标签"><select data-kind aria-label="记录类型">${opts([['','全部记录'],['automatic','创作记录'],['template','我的模板']],'')}</select><label><input data-favorite type="checkbox"> 收藏</label><button data-search-go>搜索</button></div><p data-path class="helper"></p><div class="row">${!onChoose?'<button data-new class="primary">新建提示词</button>':''}<button data-trash>回收站</button></div><div data-list class="prompt-entry-list"></div><div class="row"><button data-prev>上一页</button><span data-count></span><button data-next>下一页</button></div></section><section data-detail class="panel"><h3>选择提示词</h3><p>先按用途和模型查找，再查看或编辑内容。</p></section></div>`;
  const tree=()=>{
    root.querySelector('[data-tree]').innerHTML=['video','image','script'].map(id=>[id,catalog.purposes[id]]).map(([id,name])=>`<section><button data-purpose="${id}" class="text-link">${esc(name)}</button>${id===filters.purpose?`<div class="prompt-branches"><button data-branch="" class="${!filters.branch&&!filters.unclassified?'active':''}">全部模型</button>${catalog.branches.filter(b=>b.purpose===id&&Boolean(b.deleted_at)===Boolean(filters.trash)).map(b=>`<button data-branch="${esc(b.id)}" class="${filters.branch===b.id?'active':''}">${esc(b.name)}</button>`).join('')}<button data-unclassified class="${filters.unclassified?'active':''}">待归类</button>${!onChoose?'<button class="quiet" data-new-branch>＋ 新增分支</button>':''}</div>`:''}</section>`).join('');
    root.querySelectorAll('[data-purpose]').forEach(b=>b.onclick=()=>{filters.purpose=b.dataset.purpose;filters.branch='';filters.unclassified='';offset=0;tree();load();});
    root.querySelectorAll('[data-branch]').forEach(b=>b.onclick=()=>{filters.branch=b.dataset.branch;filters.unclassified='';offset=0;tree();load();});
    root.querySelector('[data-unclassified]')?.addEventListener('click',()=>{filters.branch='';filters.unclassified='1';offset=0;tree();load();});
    root.querySelector('[data-new-branch]')?.addEventListener('click',async()=>{await editBranch(catalog,null,filters.purpose,signal);if(alive()){catalog=await promptCatalog(signal);tree();load();}});
    if(!onChoose&&filters.branch){const b=catalog.branches.find(b=>b.id===filters.branch);if(b){const manage=document.createElement('button');manage.textContent='管理此分支';manage.dataset.manageCategory='1';root.querySelector('[data-tree]').append(manage);manage.onclick=async()=>{await editBranch(catalog,b,filters.purpose,signal);if(alive()){catalog=await promptCatalog(signal);if(Boolean(catalog.branches.find(x=>x.id===b.id)?.deleted_at)!==Boolean(filters.trash))filters.branch='';tree();load();}};}}
  };
  async function mutate(data){
    if(busy||!selected)return;busy=true;
    try{selected=await promptApi('/entries/'+selected.id,'POST',{revision:selected.revision,...data},signal);if(alive()){detail();await load(false);}}
    catch(e){if(alive())showError(e);}finally{busy=false;}
  }
  function showError(e){const box=root.querySelector('[data-detail]');box.innerHTML=errorFeedback(e)+'<button data-detail-retry>重新读取</button>';bindErrorFeedback(box);box.querySelector('button[data-detail-retry]').onclick=()=>load();}
  function detail(){
    if(!selected)return;
    const s=selected,box=root.querySelector('[data-detail]'),b=catalog.branches.find(b=>b.id===s.branch);
    const source=s.source||{};
    box.innerHTML=`<h3>${esc(s.title)}</h3><p class="helper">${esc(catalog.purposes[s.purpose])} / ${esc(b?.name||'待归类')} · ${s.record_kind==='automatic'?'创作记录':'我的模板'} · 版本 ${s.version}</p><pre class="prompt-text">${esc(contentText(s.content))}</pre><div class="row"><button data-copy>复制</button><button data-star>${s.favorite?'取消收藏':'收藏'}</button>${onChoose?'<button data-use class="primary">选择此提示词</button>':'<button data-edit>编辑</button><button data-copy-template>另存副本</button>'}</div><details><summary>版本与来源</summary>${s.source_project?`<p>来源项目：${projectOriginLink(s.source_project)}</p>`:source.external?'<p>外部素材包来源，未关联本机同编号项目。</p>':''}<p>模型家族：${esc(source.family||'未记录')}<br>底模：${esc(source.model||'未记录')}</p><div data-versions></div><button data-history>查看内容版本</button></details>${!onChoose?`<details><summary>分类与整理</summary><label class="field"><span>移动到分类</span><select data-move-branch>${opts([['','待归类'],...catalog.branches.filter(b=>!b.deleted_at).map(b=>[b.id,catalog.purposes[b.purpose]+' / '+b.name])],s.branch||'')}</select></label><div class="row"><button data-move>移动</button>${b?'<button data-manage-branch>管理当前分支</button>':''}<button data-remove>${s.deleted_at?'恢复提示词':'移除提示词'}</button></div></details>`:''}`;
    box.querySelector('[data-copy]').onclick=async()=>{try{await navigator.clipboard.writeText(contentText(s.content));toast('已复制');}catch(e){toast('复制失败，请选中文字手动复制');}};
    box.querySelector('[data-star]').onclick=()=>mutate({favorite:!s.favorite});
    box.querySelector('[data-use]')?.addEventListener('click',()=>onChoose(structuredClone(s)));
    const edit=async copy=>{const value=await openEditor({catalog,entry:s,copy,signal});if(value&&alive()){selected=value;detail();load(false);}};
    box.querySelector('[data-edit]')?.addEventListener('click',()=>edit(false));box.querySelector('[data-copy-template]')?.addEventListener('click',()=>edit(true));
    box.querySelector('[data-move]')?.addEventListener('click',()=>{const id=box.querySelector('[data-move-branch]').value;const branch=catalog.branches.find(b=>b.id===id);mutate({branch:id||null,purpose:branch?.purpose||s.purpose});});
    box.querySelector('[data-manage-branch]')?.addEventListener('click',async()=>{await editBranch(catalog,b,s.purpose,signal);if(alive()){catalog=await promptCatalog(signal);tree();load();}});
    box.querySelector('[data-remove]')?.addEventListener('click',async()=>{const choice=await chooseAction({title:s.deleted_at?'恢复提示词？':'移除提示词？',message:'项目里的文字、固定版本和生成结果保留。',signal,choices:[{value:false,label:'取消'},{value:true,label:'确认'}]});if(choice)mutate({removed:!s.deleted_at});});
    box.querySelector('[data-history]').onclick=async()=>{try{const history=await promptApi('/entries/'+s.id+'/versions','GET',undefined,signal);if(!alive()||selected?.id!==s.id||!box.contains(box.querySelector('[data-versions]')))return;box.querySelector('[data-versions]').innerHTML=history.items.map(v=>`<details><summary>版本 ${v.version}</summary><pre class="prompt-text">${esc(contentText(v.content))}</pre><button data-old-version="${v.version}">${onChoose?'选择此版本':'另存此版本'}</button></details>`).join('');box.querySelectorAll('[data-old-version]').forEach(button=>button.onclick=async()=>{const old=await promptApi('/entries/'+s.id+'/versions/'+button.dataset.oldVersion,'GET',undefined,signal);if(!alive())return;if(onChoose)onChoose(old);else await openEditor({catalog,entry:old,copy:true,signal});});}catch(e){if(alive())showError(e);}};
  }
  async function load(clear=true){
    const n=++serial;root.querySelector('[data-list]').innerHTML='<p class="helper" role="status">正在读取提示词…</p>';if(clear){selected=null;root.querySelector('[data-detail]').innerHTML='<h3>选择提示词</h3>';}
    const b=catalog.branches.find(b=>b.id===filters.branch);
    root.querySelector('[data-path]').textContent=(globalSearch?'全库（视频、图片、剧本）':`${catalog.purposes[filters.purpose]} / ${filters.unclassified?'待归类':b?.name||'全部模型'}`)+(filters.trash?' / 回收站':'');
    const query=globalSearch?{...filters,purpose:'',branch:'',unclassified:''}:filters;
    try{const data=await promptApi('/entries?'+new URLSearchParams({...query,offset,limit:20}),'GET',undefined,signal);if(!alive()||n!==serial)return;
      root.querySelector('[data-list]').innerHTML=data.items.map(s=>`<button data-entry="${s.id}" class="prompt-entry"><strong>${esc(s.title)}</strong><span>${esc(contentText(s.content).slice(0,110))}</span><small>${s.favorite?'★ · ':''}${s.record_kind==='automatic'?'创作记录':'模板'} · ${esc(catalog.branches.find(b=>b.id===s.branch)?.name||'待归类')}</small></button>`).join('')||'<p class="helper">此分类暂无提示词。保存项目后会自动收录，也可以新建模板。</p>';
      root.querySelector('[data-count]').textContent=`${data.total} 条`;root.querySelector('[data-prev]').disabled=offset===0;root.querySelector('[data-next]').disabled=offset+data.items.length>=data.total;
      root.querySelectorAll('[data-entry]').forEach(b=>b.onclick=()=>{selected=data.items.find(s=>s.id===b.dataset.entry);detail();if(innerWidth<1000)root.querySelector('[data-detail]').scrollIntoView({block:'start'});});
    }catch(e){if(alive()&&n===serial)showError(e);}
  }
  root.querySelector('[data-new]')?.addEventListener('click',async()=>{const value=await openEditor({catalog,purpose:filters.purpose,branch:filters.branch||undefined,signal});if(value&&alive()){selected=value;detail();load(false);}});
  root.querySelector('[data-search-go]').onclick=()=>{filters.q=root.querySelector('[data-search]').value;offset=0;load();};
  root.querySelector('[data-search]').onkeydown=e=>{if(e.key==='Enter')root.querySelector('[data-search-go]').click();};
  root.querySelector('[data-kind]').onchange=e=>{filters.kind=e.target.value;offset=0;load();};
  root.querySelector('[data-favorite]').onchange=e=>{filters.favorite=e.target.checked?'1':'';offset=0;load();};
  root.querySelector('[data-trash]').onclick=e=>{filters.trash=filters.trash?'':'1';filters.branch='';offset=0;e.target.textContent=filters.trash?'返回正常列表':'回收站';tree();load();};
  root.querySelector('[data-prev]').onclick=()=>{offset=Math.max(0,offset-20);load();};root.querySelector('[data-next]').onclick=()=>{offset+=20;load();};
  const scope=document.createElement('label');scope.innerHTML='<input type="checkbox" data-global-search> 全库查找';root.querySelector('.prompt-filters').append(scope);
  scope.querySelector('input').onchange=e=>{globalSearch=e.target.checked;offset=0;load();};
  tree();await load();
}
