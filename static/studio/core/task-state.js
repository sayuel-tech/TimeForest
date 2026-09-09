/** Shared task facts; modes may add domain phases without redefining uncertainty. */
export const TASK_STATES={waiting:'等待通道',queued:'排队中',preparing:'准备中',submitting:'提交中',running:'执行中',stopping:'正在停止',unknown:'待确认提交',success:'已完成',done:'已完成',complete:'已完成',accepted:'已完成',needs_review:'等待审核',interrupted:'已中断',failed:'未完成',cancelled:'已取消'};
Object.assign(TASK_STATES,{succeeded:'已完成',completed:'已完成',cancel_requested:'正在停止',submission_unknown:'待确认提交',waiting_dependency:'等待上游片段',waiting_resource:'等待通道'});
