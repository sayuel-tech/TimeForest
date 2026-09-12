import {esc,scopedModal} from './primitives.js';
import {bindTimecodeInputs,formatTimecode} from './timecode-input.js';

/** Presentation-only adapters. They move existing nodes, never replace their handlers. */
function el(tag,cls,text=''){const node=document.createElement(tag);node.className=cls;node.textContent=text;return node;}
function textOf(payload){
  if(!payload)return '';
  if(typeof payload==='string')return payload;
  if(payload.blocks)return payload.blocks.map(b=>[b.heading,b.text].filter(Boolean).join('\n')).join('\n\n');
  if(typeof payload.prompt_text==='string')return payload.prompt_text;
  if(typeof payload.replacement_text==='string')return payload.replacement_text;
  const list=payload.shots||payload.segments||payload.needs;
  if(Array.isArray(list))return list.map((row,i)=>[row.title||row.name||`第 ${i+1} 项`,row.text||row.description,Number.isFinite(row.planned_seconds)?`${row.planned_seconds} 秒`:null].filter(Boolean).join('\n')).join('\n\n');
  return JSON.stringify(payload,null,2);
}
function compareRecordedCandidates(ctx){
  const scope=ctx.writingScope;
  if(!scope)return;
  const p=ctx.session.project;
  // The visible selectors are the authoritative scope chosen by the existing adapter.
  const visible=new Set([...ctx.root.querySelectorAll('[data-output]')].map(b=>b.dataset.output));
  const candidates=(p.candidates||[]).filter(c=>visible.has(c.candidate_id)&&c.disposition!=='discarded');
  if(candidates.length<2)return;
  const options=candidates.map((c,i)=>`<option value="${esc(c.candidate_id)}">输出 ${i+1}${c.disposition==='applied'?' · 已应用':''}</option>`).join('');
  const modal=scopedModal(`<div class="dialog-heading"><span class="eyebrow">版本对照</span><h2>比较已记录的输出</h2><p>只读比较，不切换当前编辑稿，也不改变已确认内容；未保存修改不在此比较中。</p></div><div class="experience-compare"><section><select data-compare-left aria-label="左侧记录">${options}</select><pre data-compare-text-left></pre></section><section><select data-compare-right aria-label="右侧记录">${options}</select><pre data-compare-text-right></pre></section></div><div class="dialog-actions"><button type="button" data-compare-close>关闭对照</button></div>`);
  const left=modal.querySelector('[data-compare-left]'),right=modal.querySelector('[data-compare-right]');
  left.value=candidates.at(-2).candidate_id;right.value=candidates.at(-1).candidate_id;
  const show=()=>{modal.querySelector('[data-compare-text-left]').textContent=textOf(candidates.find(c=>c.candidate_id===left.value)?.payload);modal.querySelector('[data-compare-text-right]').textContent=textOf(candidates.find(c=>c.candidate_id===right.value)?.payload);};
  ctx.session.controller.signal.addEventListener('abort',()=>modal.close(),{once:true});
  left.onchange=show;right.onchange=show;modal.querySelector('[data-compare-close]').onclick=()=>modal.close();show();
}

export function enhanceAuthoringWorkspace(ctx){
  const {root}=ctx;
  const box=root.querySelector('[data-authoring-assist]');
  root.dataset.experiencePage=['intent','writing','binding','storyboard','prompt'][ctx.step]||'writing';
  if(ctx.step>=3&&ctx.selected){
    const layers=ctx.session.project.content.layers,shots=layers.find(l=>l.layer==='storyboard')?.content.shots||[],segments=layers.find(l=>l.layer==='segment')?.content.segments||[];
    const segment=segments.find(s=>s.ref===ctx.selected),shot=shots.find(s=>s.ref===(segment?.shot_ref||ctx.selected)),heading=root.querySelector('.desk-canvas > h2');
    if(shot&&heading)heading.textContent=segment?`分镜 ${shots.indexOf(shot)+1} · ${shot.title||'未命名'} / 片段 ${segments.filter(s=>s.shot_ref===shot.ref).indexOf(segment)+1}`:`分镜 ${shots.indexOf(shot)+1} · ${shot.title||'未命名'}`;
  }
  if(ctx.step===2){const writing=root.querySelector('.creation-asset-writing'),heading=writing?.querySelector(':scope > h2'),switcher=writing?.querySelector('[data-asset-task=asset_screenplay]');if(heading&&switcher){const bar=el('div','asset-writing-header');heading.before(bar);bar.append(heading,switcher);}
    const analyze=root.querySelector('[data-asset-task=asset_analysis]'),toolbar=root.querySelector('.asset-needs-toolbar');if(analyze&&toolbar){analyze.textContent='分析资产需求';toolbar.append(analyze);}const handoffs=root.querySelector('[data-view-key="image-handoffs"]');if(handoffs&&toolbar)toolbar.append(handoffs);const row=writing?.querySelector(':scope > .row');if(row&&!row.children.length)row.remove();}
  if(!box||box.dataset.experienceArranged)return;
  box.dataset.experienceArranged='true';
  const conversation=box.querySelector(':scope > .creation-assist');
  const output=el('section','writing-output-zone');output.dataset.viewScroll='writing-output';
  output.setAttribute('aria-label','当前输出与已记录版本');
  [...box.childNodes].filter(n=>n!==conversation).forEach(n=>output.append(n));
  if(conversation){
    conversation.classList.add('writing-conversation');conversation.setAttribute('aria-label','与 AI 沟通');
    if(ctx.step!==2)conversation.classList.add('writing-dialogue-expanded');
    const options=el('details','writing-options');options.dataset.viewKey='writing-options:'+ctx.step+':'+(ctx.selected||'project');options.append(el('summary','','创作依据与参考'));
    const basis=conversation.querySelector('[data-writing-basis]')?.closest('.field'),images=conversation.querySelector(':scope > .check');
    if(basis)options.append(basis);if(images)options.append(images);conversation.append(options);
    if(ctx.step===1){
      const story=root.querySelector('.desk-canvas > .reading-disclosure');
      if(story){const toggle=options.querySelector(':scope > summary');toggle.textContent='故事起点与创作依据';toggle.after(story);}
    }
    if(ctx.step===2){const header=root.querySelector('.asset-writing-header');if(header){header.append(options);conversation.querySelector('h3')?.setAttribute('hidden','');}}
  }
  box.append(output);box.classList.add('writing-surface');
  const heading=output.querySelector(':scope > h3');
  if(heading){
    const bar=el('div','writing-output-heading');heading.before(bar);bar.append(heading);
    heading.textContent='当前输出';
    const versions=output.querySelector(':scope > .row');if(versions){versions.classList.add('writing-version-choices');versions.setAttribute('aria-label','选择要查看的输出');bar.append(versions);}
    const candidateCount=output.querySelectorAll('[data-output]').length;
    if(candidateCount>1){const compare=el('button','quiet','比较版本');compare.type='button';compare.dataset.experienceCompare='';compare.onclick=()=>compareRecordedCandidates(ctx);bar.append(compare);}
  }
  const instruction=box.querySelector('[data-ai-instruction]');if(instruction){instruction.rows=ctx.step===2?2:3;instruction.setAttribute('aria-label','本次修改要求');}
  output.querySelectorAll('textarea').forEach(t=>t.dataset.viewScroll='writing-text');
  const summary=output.querySelector('details[data-view-key^="candidate:"] > summary');
  if(summary){
    summary.classList.add('writing-version-label');
    summary.textContent=summary.textContent.replace('AI 返回的候选 · ','').replace('尚未写入正文','本次输出 · 尚未确认').replace('已保存内容，可继续编辑','已应用内容 · 可继续编辑');
  }
  // Keep version actions outside the disclosure: choosing a version must not fold the output.
  if(!summary&&!output.querySelector('.writing-output')){
    const empty=el('p','writing-output-empty','在上方写下想法或修改要求，返回的内容会显示在这里，核对后再确认。');
    output.append(empty);
  }
  // A long history is auxiliary, never another document-sized panel above the output.
  const history=output.querySelector('details[data-view-key^="writing-history:"]');
  if(history){history.classList.add('writing-conversation-history');history.dataset.viewScroll='writing-history';}
  const saved=root.querySelectorAll('.desk-canvas > .saved-writing,.creation-asset-writing > .saved-writing');
  saved.forEach(d=>{d.classList.add('writing-source-disclosure');output.append(d);});
  const status=output.querySelector('[data-creation-status]');if(status&&['succeeded','cancelled'].includes(ctx.writingJob?.state))output.append(status);
}

function safeMediaURL(value){
  if(typeof value!=='string'||!value)return '';
  try{const url=new URL(value,document.baseURI);return ['http:','https:','blob:'].includes(url.protocol)?value:'';}catch{return '';}
}
function addThumbnail(button,url,{timeline=false}={}){
  if(button.querySelector('.candidate-media'))return;
  const media=el('span','candidate-media');media.setAttribute('aria-hidden','true');
  const source=safeMediaURL(url);
  if(source){
    const video=document.createElement('video');video.muted=true;video.playsInline=true;video.preload='metadata';video.tabIndex=-1;video.src=source;video.setAttribute('aria-hidden','true');
    video.addEventListener('loadedmetadata',()=>{if(Number.isFinite(video.duration)&&video.duration>0)video.currentTime=Math.min(.001,video.duration/2);},{once:true});
    media.append(video);

  }
  media.append(el('span','candidate-media-symbol',timeline?'▥':'▶'));
  button.prepend(media);
}
export function enhanceMovieWorkspace({ctx,project,edit,mediaURL,currentTake,source,mark}){
  const root=ctx.root;root.dataset.experiencePage=ctx.step===0?'generation':'editing';
  const canvas=root.querySelector('.desk-canvas');if(!canvas||canvas.dataset.movieExperienceArranged)return;
  canvas.dataset.movieExperienceArranged='true';
  if(ctx.step===0){
    const choices=(project.movie_takes||[]).filter(t=>t.movie_segment_id===ctx.selected&&t.state!=='removed');
    const currentSource=source(ctx.selected),heading=canvas.querySelector(':scope > h2');
    if(currentSource&&heading)heading.textContent=`${currentSource.shot.title||'分镜'} · 片段 ${project.content.segment_order.indexOf(ctx.selected)+1}`;
    const formal=canvas.querySelector(':scope > .reading-disclosure'),sourcePanel=root.querySelector('#property-source');
    if(formal&&sourcePanel)sourcePanel.append(formal);
    const viewedPlayer=canvas.querySelector(':scope > .media-player');
    if(viewedPlayer&&currentTake){
      const adopted=choices.findIndex(t=>t.currently_adopted),viewed=choices.indexOf(currentTake);
      const receipt=el('div','movie-viewing-heading');receipt.setAttribute('role','status');
      receipt.append(el('strong','',`正在查看 · 候选 ${viewed+1}`),el('span','',adopted<0?'尚未采用结果':adopted===viewed?'此结果已采用':`当前采用候选 ${adopted+1} · 查看不会替换`));
      viewedPlayer.before(receipt);
    }
    const buttons=[...root.querySelectorAll('[data-run-view]')];
    if(buttons.length){
      const gallery=buttons[0].parentElement;gallery.classList.add('candidate-gallery');gallery.setAttribute('aria-label','候选结果：查看不等于采用');
      buttons.forEach((button,index)=>{
        const take=choices.find(t=>t.take_id===button.dataset.runView);if(!take)return;
        button.classList.add('candidate-tile');
        const meta=el('span','candidate-meta');while(button.firstChild)meta.append(button.firstChild);button.append(meta);
        addThumbnail(button,mediaURL(take));
        button.setAttribute('aria-label',`查看候选 ${index+1}${take.currently_adopted?'，当前已采用':''}${take.library_asset?'，已入库':''}`);
        button.dataset.viewing=String(currentTake?.take_id===take.take_id);
        button.dataset.adopted=String(!!take.currently_adopted);
      });
      const player=canvas.querySelector(':scope > .media-player');
      if(player){player.after(gallery);const caption=el('div','candidate-section-caption','候选结果');gallery.before(caption);caption.append(el('small','','点击查看；采用与入库是独立操作。'));}
    }
    const adopt=root.querySelector('[data-adopt]');if(adopt)adopt.textContent=currentTake?.currently_adopted?'当前已采用':'采用此结果';
    const sourceLink=root.querySelector('[data-take-source]');if(sourceLink)sourceLink.textContent='本次制作记录';
  }else{
    const controls=canvas.querySelector('.movie-item-controls');
    const timeline=canvas.querySelector('.movie-timeline');
    if(controls&&timeline){
      const player=controls.querySelector('.media-player');
      if(player){
        const preview=el('div','movie-preview-row'),facts=el('aside','movie-edit-facts');
        const included=edit.items.filter(i=>i.included&&edit.order.includes(i.id));
        facts.innerHTML=`<b>${esc(project.name)}</b><strong>${formatTimecode(included.reduce((n,i)=>n+i.range.out_ms-i.range.in_ms,0))}</strong><p>当前预览所选片段；连续预览按轨道顺序播放。</p>`;
        controls.before(preview);preview.append(player,facts);preview.after(timeline);
        const zoom=canvas.querySelector('[data-zoom]')?.closest('label');if(zoom)timeline.prepend(zoom);
        const previewButton=canvas.querySelector('[data-preview-edit]'),exportButton=root.querySelector('[data-export]');if(previewButton&&exportButton)exportButton.before(previewButton);
      }
    }
    root.querySelectorAll('[data-item]').forEach((button,index)=>{
      const item=edit.items.find(i=>i.id===button.dataset.item);if(!item)return;
      const take=(project.movie_takes||[]).find(t=>t.take_id===item.take_id);
      const src=source(item.movie_segment_id);
      const title=src?.segment?.title||src?.segment?.text?.split(/[。\n]/)[0]?.slice(0,28)||src?.shot?.title||`片段 ${index+1}`;
      addThumbnail(button,mediaURL(take),{timeline:true});
      const label=el('span','movie-clip-title',title);button.append(label);
      button.setAttribute('aria-label',`${title}，采用 ${formatTimecode(item.range.out_ms-item.range.in_ms)}${item.included?'':'，已排除'}。可拖动或用下方前移后移调整。`);
    });
    if(controls){const title=controls.querySelector(':scope > h3'),actions=controls.querySelector(':scope > .row');if(title&&actions){const heading=el('div','movie-item-heading');title.before(heading);heading.append(title,actions);}}
    const selected=edit.items.find(i=>i.id===ctx.selectedItem);
    const take=selected&&(project.movie_takes||[]).find(t=>t.take_id===selected.take_id);
    if(controls&&selected){
      const index=edit.order.indexOf(selected.id),src=source(selected.movie_segment_id);
      const title=src?.segment?.title||src?.segment?.text?.split(/[。\n]/)[0]?.slice(0,28)||src?.shot?.title||'未命名片段';
      controls.querySelector('.movie-item-heading h3').textContent=`轨道 ${index+1} · ${title}`;
      controls.querySelector('[data-move="-1"]').disabled=index<=0;
      controls.querySelector('[data-move="1"]').disabled=index>=edit.order.length-1;
      const summary=el('span','movie-trim-summary',`${selected.included?'纳入成片':'已排除，不参与导出'} · 保留 ${formatTimecode(selected.range.out_ms-selected.range.in_ms)} · 原片 ${formatTimecode(take?.duration_ms||0)}`);
      controls.querySelector('.movie-item-heading h3').append(summary);
      controls.querySelectorAll('[data-range]').forEach(input=>input.addEventListener('input',()=>{
        const start=Number(controls.querySelector('[data-range="in_ms"]').value),end=Number(controls.querySelector('[data-range="out_ms"]').value);
        summary.textContent=end>start?`${selected.included?'纳入成片':'已排除，不参与导出'} · 保留 ${formatTimecode(end-start)} · 原片 ${formatTimecode(take?.duration_ms||0)}`:'出点须晚于入点 · 当前区间尚未保存';
      }));
      const relation=controls.querySelector(':scope > h3');
      if(relation)relation.textContent=`来源 · ${src?.shot?.title||'分镜'} · 剧本片段 ${project.content.segment_order.indexOf(selected.movie_segment_id)+1}`;
    }
    bindTimecodeInputs(root,{duration:take?.duration_ms,onDraftInput:mark,drafts:ctx.timecodeDrafts,scope:'edit:'+ctx.selectedItem});
    const header=canvas.querySelector(':scope > .row');
    if(header&&!header.querySelector('.movie-edit-summary')){
      const included=edit.items.filter(i=>i.included&&edit.order.includes(i.id));
      header.append(el('span','movie-edit-summary',`${included.length} 个采用片段 · ${formatTimecode(included.reduce((n,i)=>n+i.range.out_ms-i.range.in_ms,0))}`));
    }
  }
  bindTimecodeInputs(root,{onDraftInput:mark,drafts:ctx.timecodeDrafts,scope:'generation:'+ctx.selected});
}
