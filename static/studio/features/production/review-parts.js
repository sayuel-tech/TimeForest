import {candidateState,resultActions,collectionActions} from '../../ui/result-view.js';
import {resultAsset} from '../asset-picker/result-import.js';
import {errorFeedback} from '../../ui/error-feedback.js';
import {mediaPlayer} from '../../ui/media-player.js';
import {propertyTabs} from '../../ui/workbench.js';
import {recordControl,removedRecords} from '../../ui/candidate-records.js';

export function selectionLabel(ctx,s){return ctx.project.segments?.every(x=>x.id===s.id||['accepted','done'].includes(x.status))?'选用并合成':'选用此结果';}
export function videoCandidateHistory(ctx,s){
  const visible=s.attempts.filter(a=>!a.removed_at);
  const history=visible.map(a=>{
    const selected=s.selected===a.id&&['accepted','done'].includes(s.status),asset=resultAsset(ctx,'candidate',a.id);
    return `<details class="attempt" data-source-run="${ctx.esc(a.id)}" ${ctx.sourceRun===a.id?'open':''}><summary>候选 ${s.attempts.indexOf(a)+1} · ${ctx.LABELS[a.status]||ctx.esc(a.status)}${candidateState({selected,collected:Boolean(asset)})}</summary><p class="helper">展开仅查看，不改变选用结果。</p><p>种子 ${ctx.esc(a.seed)} · ${new Date(a.created*1000).toLocaleString()}</p>${a.tasks?`<p>内部任务 ${a.completed_tasks||0}/${a.tasks.length}</p>${a.tasks.map((t,i)=>`<p>任务${i+1} · ${ctx.LABELS[t.status]||ctx.esc(t.status)} · 种子 ${ctx.esc(t.last_seed??'尚未生成')}</p>`).join('')}`:''}${a.error?errorFeedback(a.error):''}${a.delivery_url?mediaPlayer(a.delivery_url,'候选'+(s.attempts.indexOf(a)+1)):''}${resultActions({inspect:`<button type="button" data-attempt="${ctx.esc(a.id)}">查看实际运行文件</button>`,decide:a.delivery_url?`<button type="button" data-select-attempt="${ctx.esc(a.id)}" ${selected||ctx.project.busy?'disabled':''}>${selected?'已选用':selectionLabel(ctx,s)}</button>`:'',collect:a.delivery_url?collectionActions({url:a.delivery_url,asset,button:ctx.catalog.asset_library_version?`<button type="button" class="quiet" data-publish-candidate="${ctx.esc(a.id)}">加入资产库</button>`:''}):''})}${recordControl(a,{selected:s.selected===a.id,busy:ctx.project.busy})}</details>`;
  }).join('');
  return history+removedRecords(s.attempts,{busy:ctx.project.busy});
}

export function reviewProperties(ctx,s) {
  const refs=ctx.localAssets(s).map(a=>`<figure class="review-reference">${a.kind==='image'?`<img src="${ctx.esc(a.url)}" alt="${ctx.esc(a.name)}">`:`<audio controls preload="metadata" src="${ctx.esc(a.url)}"></audio>`}<figcaption>${ctx.esc(a.name)}</figcaption></figure>`).join('');
  const history=videoCandidateHistory(ctx,s);
  return propertyTabs(ctx,[{id:'references',label:'参考',html:refs||'<p>本段未使用独立参考素材。</p>'},{id:'runs',label:'运行',html:ctx.executionCard(s)+(history||'<p>尚未生成，没有运行记录。</p>')},{id:'script',label:'正文',html:`<p class="helper">当前编排原文；实际提交正文请在运行文件中查看。</p><pre>${ctx.esc(s.prompt)}</pre>`}]);
}

export function reviewActions(ctx,s,finalReview) {
  const p=ctx.project;
  return resultActions({note:`<span class="run-note">种子 ${ctx.esc(s.last_seed??'尚未生成')} · 下次${s.seed_mode==='random'?'随机':'固定 '+ctx.esc(s.seed)}</span>`,decide:`${s.status==='needs_review'?(finalReview?'<button id="approve" class="primary">选用并合成</button>':'<button id="approve" class="primary">选用并继续制作</button><button id="accept-only">选用此结果</button>'):''}${s.status==='interrupted'?'<button id="recover">查询并恢复结果</button>'+(p.storyboard_version?'<button id="resume-story">继续未完成任务</button>':''):''}${!p.busy&&['draft','ready','failed'].includes(s.status)?`<button id="run-one" class="primary" data-auto-save data-saved-label="生成本段" data-dirty-label="保存并生成本段">${ctx.dirty?'保存并生成本段':'生成本段'}</button>`:''}${!p.busy&&['needs_review','accepted','done','failed'].includes(s.status)?'<button id="reroll">重新生成本段</button>':''}`,collect:s.delivery_url?collectionActions({url:s.delivery_url,asset:resultAsset(ctx,'candidate',s.selected),button:s.selected&&ctx.catalog.asset_library_version?`<button type="button" class="quiet" data-publish-candidate="${s.selected}">加入资产库</button>`:''}):''});
}
