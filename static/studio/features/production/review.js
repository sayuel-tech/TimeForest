import {addRecordButton,recordSource} from '../prompt-library/records.js';
import {workbench,bindWorkbench} from '../../ui/workbench.js';
import {shotHeading} from '../prompts/authoring.js';
import {reviewProperties,reviewActions,selectionLabel,videoCandidateHistory} from './review-parts.js';
import { finishesReview } from "../../core/export-lifecycle.js";
import {bindErrorFeedback} from '../../ui/error-feedback.js';
import {recordConfirmation} from '../../ui/candidate-records.js';

/** View feature; receives a project-scoped public workspace context. */
export function createFeature(ctx) {
  function renderReview() {
    const p = ctx.project,
      s = p.segments[ctx.shot];
    const finalReview = finishesReview(p, ctx.shot);
    const rail=`<h3>制作进度</h3><div class="shot-nav">${p.segments.map((segment,i)=>`<button data-shot="${i}" class="${i===ctx.shot?'active':''}">P${i+1} · ${ctx.LABELS[segment.status]||segment.status}</button>`).join('')}</div>`;
    const canvas=s?shotHeading(ctx,s)+`<div class="review-media">${ctx.reviewComparison(s)}</div>`+reviewActions(ctx,s,finalReview)+`<section class="review-candidates"><h3>候选结果</h3><p class="helper">查看、选用和加入资产库是独立操作。</p>${videoCandidateHistory(ctx,s)}</section>`:'<p>先在编排准备片段。</p>';
    ctx.$('#view').innerHTML=`${p.mode==='swap'&&!p.source_ready?'<div class="notice">当前参数需要重新准备源切片，无需重新上传。<button id="review-source">前往源视频准备</button></div>':''}<div id="run-progress">${ctx.progressCard()}</div><div class="review-toolbar"><div>${ctx.field('执行方式',`<select id="review-mode">${ctx.opts([['manual','人工逐段审核'],['automatic','全自动生成并合成']],p.review)}</select>`)}</div><div class="row"><button id="run-preflight" data-auto-save data-saved-label="检查工作流" data-dirty-label="保存并检查工作流">检查工作流</button>${p.busy?'<button id="pause">完成本段后暂停</button>':`<button id="run-all" ${p.review==='automatic'?'class="primary"':''} data-auto-save data-saved-label="${p.review==='automatic'?'生成全部并自动合成':'开始逐段制作'}" data-dirty-label="保存并开始制作">${ctx.dirty?'保存并开始制作':p.review==='automatic'?'生成全部并自动合成':'开始逐段制作'}</button>`}</div></div>${ctx.dirty?'<div class="notice review-draft"><p id="review-draft-note">生成前将自动保存；涉及结果过期或切换工作流时先确认。</p><button id="save-review">保存修改</button><button id="discard-review">放弃修改</button></div>':''}${workbench({kind:'review-desk',rail,canvas,inspector:s?reviewProperties(ctx,s):''})}`;
    bindWorkbench(ctx);bindErrorFeedback(ctx.root);
    if (ctx.$("#review-source"))
      ctx.$("#review-source").onclick = () => ctx.switchTab("source");
    if (ctx.$("#save-review")) ctx.$("#save-review").onclick = ctx.save;
    if (ctx.$("#discard-review"))
      ctx.$("#discard-review").onclick = async () => {
        if (
          await ctx.confirm(
            "放弃未保存修改？",
            "恢复上次保存的制作参数与编排。",
            "放弃修改",
          )
        )
          await ctx.loadProject(ctx.project.id);
      };
    ctx.$("#review-mode").onchange = (e) => {
      p.review = e.target.value;
      ctx.setDirty();
      ctx.renderProject();
    };
    ctx.$("#run-preflight").onclick = ctx.preflight;
    if (ctx.$("#run-all"))
      ctx.$("#run-all").onclick = () =>
        ctx.runAction("/generate", { all: true });
    if (ctx.$("#pause"))
      ctx.$("#pause").onclick = () => ctx.runAction("/pause", {});
    document.querySelectorAll("[data-shot]").forEach(
      (b) =>
        (b.onclick = () => {
          ctx.shot = Number(b.dataset.shot);
          ctx.renderProject();
        }),
    );
    if (!s) return;
    ctx.root.querySelectorAll('[data-attempt]').forEach(anchor=>addRecordButton(anchor,{path:'/records/'+p.id+'?run='+encodeURIComponent(anchor.dataset.attempt),signal:ctx.session.controller.signal,apply:row=>{if(ctx.session.disposed||ctx.project!==p||ctx.working||ctx.actionPending)throw new Error('目标已变化或正在操作，请重新打开');if(p.mode==='swap'){s.swap_prompt_mode='custom';s.swap_custom_prompt=row.content.text;}else{s.prompt_mode='full';s.prompt=row.content.text;}recordSource(s,p.mode==='swap'?'swap_custom_prompt':'prompt',row);ctx.setDirty();ctx.tab='edit';ctx.renderProject();}}));
    ctx.root.querySelectorAll('[data-record-remove],[data-record-restore]').forEach(b=>b.onclick=async()=>{
      const restore=Boolean(b.dataset.recordRestore),record=b.dataset.recordRestore||b.dataset.recordRemove;
      if(!await ctx.confirm(restore?'恢复生成记录':'移除这条生成记录？',recordConfirmation(restore),restore?'恢复':'移除'))return;
      await ctx.runAction('/records/visibility',{record,segment:s.id,removed:!restore,revision:ctx.project.revision});
    });
    ctx.root.querySelectorAll('[data-publish-candidate]').forEach(b=>b.onclick=()=>ctx.saveProjectMedia({kind:'candidate',resultId:b.dataset.publishCandidate}));
    const map = {
      "run-one": () =>
        ctx.runAction("/generate", { all: false, index: ctx.shot }),
      approve: () =>
        ctx.runAction(`/segments/${ctx.shot}/approve`, { continue: true }),
      "accept-only": () => ctx.runAction(`/segments/${ctx.shot}/approve`, {}),
      recover: () => ctx.runAction(`/segments/${ctx.shot}/recover`, {}),
      "resume-story": () => ctx.runAction(`/segments/${ctx.shot}/resume`, {}),
      reroll: async () => {
        if (
          await ctx.confirm(
            "重生成本段",
            "将创建新候选结果，取消当前选用，并使依赖本段上下文的后续结果过期；旧候选与文件保留。",
            "重新生成",
          )
        )
          ctx.runAction(`/segments/${ctx.shot}/reroll`, {});
      },
    };
    for (const [id, fn] of Object.entries(map))
      if (ctx.$("#" + id)) ctx.$("#" + id).onclick = fn;
    document.querySelectorAll("[data-select-attempt]").forEach(
      (b) =>
        (b.onclick = async () => {
          if (
            await ctx.confirm(
              selectionLabel(ctx,s)+"？",
              "若替换当前选用结果，依赖它的后续片段需要重新生成。"+(selectionLabel(ctx,s)==='选用并合成'?'所有片段通过审核后会自动合成成片。':''),
              selectionLabel(ctx,s),
            )
          )
            ctx.runAction(`/segments/${ctx.shot}/approve`, {
              attempt: b.dataset.selectAttempt,
            });
        }),
    );
    document
      .querySelectorAll("[data-attempt]")
      .forEach(
        (b) =>
          (b.onclick = () =>
            ctx.attemptDialog(
              s.attempts.find((a) => a.id === b.dataset.attempt),
            )),
      );
  }
  return { renderReview };
}
