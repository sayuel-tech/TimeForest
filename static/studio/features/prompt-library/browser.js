import {libraryNavigation} from '../../ui/library-navigation.js';
import {workspaceViewState} from '../../ui/workspace-view-state.js';
import {projectOriginLink} from '../../ui/asset-origin.js';
import {esc,opts,toast} from '../../ui/primitives.js';
import {chooseAction} from '../../ui/choice-dialog.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';
import {promptApi,promptCatalog} from './api.js';
import {openEditor,editBranch,contentText} from './editor.js';

/** Shared library browser for the full page and in-workspace selection. */
export async function mountPromptBrowser(root,{signal,purpose='video',branch,onChoose}={}){
  let catalog=await promptCatalog(signal),selected=null,offset=0,serial=0,busy=false,globalSearch=false,items=[],returnFocus=null;
  let filters={purpose,branch:branch||'',q:'',kind:'',favorite:'',trash:''},listPosition=null;
  const alive=()=>root.isConnected&&!signal?.aborted;
  const emptyDetail='<div class="prompt-detail-empty"><h3>查看提示词</h3><p class="helper">从列表选择一条，查看正文、版本和来源。</p></div>';
  root.innerHTML=`<div class="prompt-library-browser"><aside data-tree></aside><section class="prompt-results"><div class="prompt-filters"><div class="prompt-search-row"><input data-search aria-label="搜索提示词" placeholder="搜索名称、正文或标签"><button data-search-go>搜索</button></div><div class="prompt-filter-options"><select data-kind aria-label="记录类型">${opts([['','全部记录'],['automatic','创作记录'],['template','我的模板']],'')}</select><label class="check"><input data-favorite type="checkbox"> 收藏</label><label class="check"><input data-global-search type="checkbox"> 全库查找</label></div></div><div class="prompt-results-heading"><h2 data-path class="collection-path"></h2><div class="row">${!onChoose?'<button data-new class="primary">新建提示词</button>':''}<button data-trash class="quiet">回收站</button></div></div><div data-list class="prompt-entry-list"></div><div class="prompt-pagination"><button data-prev>上一页</button><span data-count></span><button data-next>下一页</button></div></section><section data-detail class="panel">${emptyDetail}</section></div>`;
  const frame=root.querySelector('.prompt-library-browser');
  frame.dataset.view='list';
  root.querySelector('[data-detail]').hidden=true;
  function view(reading){
    if(reading&&frame.dataset.view!=='read')listPosition={window:window.scrollY,dialog:root.closest('dialog')?.scrollTop||0};
    frame.dataset.view=reading?'read':'list';
    root.querySelector('[data-tree]').hidden=reading;
    root.querySelector('.prompt-results').hidden=reading;
    root.querySelector('[data-detail]').hidden=!reading;
  }
  function back(){view(false);if(listPosition){const dialog=root.closest('dialog');if(dialog)dialog.scrollTop=listPosition.dialog;else window.scrollTo({top:listPosition.window,behavior:'instant'});}returnFocus?.isConnected&&returnFocus.focus({preventScroll:true});}
  function focusReading(){const box=root.querySelector('[data-detail]'),dialog=root.closest('dialog');if(dialog)dialog.scrollTop=0;else box.scrollIntoView({block:'start',behavior:'instant'});box.querySelector('h3')?.focus({preventScroll:true});}
  const tree=()=>{
    const item=(label,data,active)=>({label,data,active});
    root.querySelector('[data-tree]').innerHTML=libraryNavigation({label:'提示词用途与模型',groups:[{label:'用途 / 模型',items:['video','image','script'].map(id=>({label:catalog.purposes[id],data:{purpose:id},expandable:true,expanded:!globalSearch&&id===filters.purpose,children:!globalSearch&&id===filters.purpose?[
      item('全部模型',{branch:''},!filters.branch&&!filters.unclassified),
      ...catalog.branches.filter(b=>b.purpose===id&&Boolean(b.deleted_at)===Boolean(filters.trash)).map(b=>item(b.name,{branch:b.id},filters.branch===b.id)),
      item('待归类',{unclassified:''},!!filters.unclassified),
    ]:[]}))},...(!onChoose?[{label:'分类管理',items:[item('＋ 新增模型分支',{'new-branch':''},false)]}]:[])]});
    const localScope=()=>{globalSearch=false;root.querySelector('[data-global-search]').checked=false;};
    root.querySelectorAll('[data-purpose]').forEach(b=>b.onclick=()=>{localScope();filters.purpose=b.dataset.purpose;filters.branch='';filters.unclassified='';offset=0;tree();load();});
    root.querySelectorAll('[data-branch]').forEach(b=>b.onclick=()=>{localScope();filters.branch=b.dataset.branch;filters.unclassified='';offset=0;tree();load();});
    root.querySelector('[data-unclassified]')?.addEventListener('click',()=>{localScope();filters.branch='';filters.unclassified='1';offset=0;tree();load();});
    root.querySelector('[data-new-branch]')?.addEventListener('click',async()=>{await editBranch(catalog,null,filters.purpose,signal);if(alive()){catalog=await promptCatalog(signal);tree();load();}});
    if(!onChoose&&filters.branch){const b=catalog.branches.find(b=>b.id===filters.branch);if(b){const manage=document.createElement('button');manage.textContent='管理此分支';manage.dataset.manageCategory='1';manage.className='collection-nav-link';root.querySelector('[data-tree]').append(manage);manage.onclick=async()=>{await editBranch(catalog,b,filters.purpose,signal);if(alive()){catalog=await promptCatalog(signal);if(Boolean(catalog.branches.find(x=>x.id===b.id)?.deleted_at)!==Boolean(filters.trash))filters.branch='';tree();load();}};}}
  };
  const detailState=workspaceViewState(root.querySelector('[data-detail]'));
  signal?.addEventListener('abort',()=>detailState.dispose(),{once:true});
  async function mutate(data){
    if(busy||!selected)return;busy=true;const original=selected;
    try{const updated=await promptApi('/entries/'+original.id,'POST',{revision:original.revision,...data},signal);if(alive()){if(selected?.id===original.id)selected=updated;await load(false);}}
    catch(e){if(alive())showError(e);}finally{busy=false;}
  }
  function showError(e){view(true);const box=root.querySelector('[data-detail]');box.innerHTML='<button data-back-list>返回列表</button>'+errorFeedback(e)+'<button data-detail-retry>重新读取</button>';box.querySelector('[data-back-list]').onclick=back;bindErrorFeedback(box);box.querySelector('button[data-detail-retry]').onclick=()=>load();}
  function detail(){
    if(!selected)return;
    const s=selected,box=root.querySelector('[data-detail]'),b=catalog.branches.find(b=>b.id===s.branch);
    const source=s.source||{},restoreDetail=detailState.beforeRender(s.id);
    root.querySelectorAll('[data-entry]').forEach(el=>{const active=el.dataset.entry===s.id;el.classList.toggle('active',active);el.setAttribute('aria-pressed',String(active));});
    box.innerHTML=`<h3>${esc(s.title)}</h3><p class="helper">${esc(catalog.purposes[s.purpose])} / ${esc(b?.name||'待归类')} · ${s.record_kind==='automatic'?'创作记录':'我的模板'} · 版本 ${s.version}</p><pre class="prompt-text">${esc(contentText(s.content))}</pre><div class="row"><button data-copy>复制</button><button data-star>${s.favorite?'取消收藏':'收藏'}</button>${onChoose?`<button data-use class="primary">选择版本 ${s.version}</button>`:'<button data-edit>编辑</button><button data-copy-template>另存副本</button>'}</div><details><summary>版本与来源</summary>${s.source_project?`<p>来源项目：${projectOriginLink(s.source_project)}</p>`:source.external?'<p>外部素材包来源，未关联本机同编号项目。</p>':''}<p>模型家族：${esc(source.family||'未记录')}<br>底模：${esc(source.model||'未记录')}</p><div data-versions></div><button data-history>查看内容版本</button></details>${!onChoose?`<details><summary>分类与整理</summary><label class="field"><span>移动到分类</span><select data-move-branch>${opts([['','待归类'],...catalog.branches.filter(b=>!b.deleted_at).map(b=>[b.id,catalog.purposes[b.purpose]+' / '+b.name])],s.branch||'')}</select></label><div class="row"><button data-move>移动</button>${b?'<button data-manage-branch>管理当前分支</button>':''}<button data-remove>${s.deleted_at?'恢复提示词':'移除提示词'}</button></div></details>`:''}`;
    view(true);
    const position=items.findIndex(item=>item.id===s.id);
    const navigation=document.createElement('nav');navigation.className='prompt-reading-navigation';navigation.setAttribute('aria-label','提示词阅读');
    navigation.innerHTML=`<button data-back-list>← 返回列表</button><span class="helper">${position<0?'当前提示词':`本页 ${position+1} / ${items.length}`}</span><div class="row"><button data-read-prev ${position<=0?'disabled':''}>上一条</button><button data-read-next ${position<0||position>=items.length-1?'disabled':''}>下一条</button></div>`;
    box.prepend(navigation);navigation.querySelector('[data-back-list]').onclick=back;
    const move=delta=>{selected=items[position+delta];returnFocus=root.querySelector(`[data-entry="${selected.id}"]`);detail();focusReading();};
    navigation.querySelector('[data-read-prev]').onclick=()=>move(-1);navigation.querySelector('[data-read-next]').onclick=()=>move(1);
    box.querySelector('h3').tabIndex=-1;
    restoreDetail();
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
    const n=++serial;root.querySelector('[data-list]').innerHTML='<p class="helper" role="status">正在读取提示词…</p>';if(clear){selected=null;view(false);root.querySelector('[data-detail]').innerHTML=emptyDetail;}
    const b=catalog.branches.find(b=>b.id===filters.branch);
    root.querySelector('[data-path]').textContent=(globalSearch?'全库（视频、图片、剧本）':`${catalog.purposes[filters.purpose]} / ${filters.unclassified?'待归类':b?.name||'全部模型'}`)+(filters.trash?' / 回收站':'');
    const query=globalSearch?{...filters,purpose:'',branch:'',unclassified:''}:filters;
    try{const data=await promptApi('/entries?'+new URLSearchParams({...query,offset,limit:20}),'GET',undefined,signal);if(!alive()||n!==serial)return;
      items=data.items;
      root.querySelector('[data-list]').innerHTML=data.items.map(s=>`<button data-entry="${s.id}" class="prompt-entry ${selected?.id===s.id?'active':''}" aria-pressed="${selected?.id===s.id}"><strong>${esc(s.title)}</strong><span>${esc(contentText(s.content).slice(0,220))}</span><small>${s.favorite?'★ · ':''}${s.record_kind==='automatic'?'创作记录':'模板'} · ${esc(catalog.branches.find(b=>b.id===s.branch)?.name||'待归类')} · 阅读全文 →</small></button>`).join('')||`<p class="helper" data-empty>${filters.q||filters.kind||filters.favorite?'没有符合当前筛选条件的提示词，请调整关键词或筛选条件。':filters.trash?'回收站暂无提示词。':onChoose?'此分类暂无提示词，可切换用途、模型或使用全库查找。':'此分类暂无提示词。保存项目后会自动收录，也可以新建模板。'}</p>`;
      root.querySelector('[data-count]').textContent=`${data.total} 条`;root.querySelector('[data-prev]').disabled=offset===0;root.querySelector('[data-next]').disabled=offset+data.items.length>=data.total;
      root.querySelectorAll('[data-entry]').forEach(b=>b.onclick=()=>{returnFocus=b;selected=items.find(s=>s.id===b.dataset.entry);detail();focusReading();});
      if(!clear&&selected){returnFocus=root.querySelector(`[data-entry="${selected.id}"]`);if(frame.dataset.view==='read')detail();}
    }catch(e){if(alive()&&n===serial)showError(e);}
  }
  root.querySelector('[data-new]')?.addEventListener('click',async()=>{const value=await openEditor({catalog,purpose:filters.purpose,branch:filters.branch||undefined,signal});if(value&&alive()){selected=value;detail();load(false);}});
  root.querySelector('[data-search-go]').onclick=()=>{filters.q=root.querySelector('[data-search]').value;offset=0;load();};
  root.querySelector('[data-search]').onkeydown=e=>{if(e.key==='Enter')root.querySelector('[data-search-go]').click();};
  root.querySelector('[data-kind]').onchange=e=>{filters.kind=e.target.value;offset=0;load();};
  root.querySelector('[data-favorite]').onchange=e=>{filters.favorite=e.target.checked?'1':'';offset=0;load();};
  root.querySelector('[data-trash]').onclick=e=>{filters.trash=filters.trash?'':'1';filters.branch='';offset=0;e.target.textContent=filters.trash?'返回正常列表':'回收站';tree();load();};
  root.querySelector('[data-prev]').onclick=()=>{offset=Math.max(0,offset-20);load();};root.querySelector('[data-next]').onclick=()=>{offset+=20;load();};
  root.querySelector('[data-global-search]').onchange=e=>{globalSearch=e.target.checked;offset=0;tree();load();};
  tree();await load();
}
