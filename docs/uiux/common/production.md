# 视频正文、审核与成片

维护 ID：`production`。关键词：审核、原片对照、播放器、候选、成片、导出、视频正文。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

前三视频的共用控制器、正文编辑、审核与成片；其他模式复用结果/播放器但保存与选用保持各自业务。

## 保留优先

保留媒体有效画面、候选与选用区分、入库独立、末段成片导航与可恢复移除。

## 修改边界及联动

每种 mode 的 reviewComparison 提供对照差异；不能修改公共播放器就裁掉原片内容。选用、入库、重新生成、继续编辑不是同一动作。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/app/workspace-controller.js](../../../static/studio/app/workspace-controller.js) | `mountWorkspace` |
| [static/studio/features/export/index.js](../../../static/studio/features/export/index.js) | `createFeature` |
| [static/studio/features/production/preflight.js](../../../static/studio/features/production/preflight.js) | `createFeature` |
| [static/studio/features/production/records.js](../../../static/studio/features/production/records.js) | `createFeature` |
| [static/studio/features/production/review-parts.js](../../../static/studio/features/production/review-parts.js) | `selectionLabel`, `videoCandidateHistory`, `reviewProperties`, `reviewActions` |
| [static/studio/features/production/review.js](../../../static/studio/features/production/review.js) | `createFeature` |
| [static/studio/features/prompts/authoring.js](../../../static/studio/features/prompts/authoring.js) | `assetCommands`, `shotProperties`, `shotHeading`, `shotPrompt` |
| [static/studio/features/prompts/editor-parts.js](../../../static/studio/features/prompts/editor-parts.js) | `projectSummary`, `savebar`, `shotNavigation`, `sourceVideo`, `sourcePlayer`, `bindEditor`, `resultPlayer` |
| [static/studio/features/prompts/index.js](../../../static/studio/features/prompts/index.js) | `createFeature` |
| [static/studio/styles/media-player.css](../../../static/studio/styles/media-player.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |
| [static/studio/ui/candidate-records.js](../../../static/studio/ui/candidate-records.js) | `recordControl`, `removedRecords`, `recordConfirmation` |
| [static/studio/ui/media-player.js](../../../static/studio/ui/media-player.js) | `mediaPlayer`, `bindMediaPlayers` |
| [static/studio/ui/result-view.js](../../../static/studio/ui/result-view.js) | `candidateState`, `candidateButton`, `resultActions`, `collectionActions` |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/production.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

相同视频不因进度刷新重建播放器；选用准确；导出状态与页签同步；移除保护当前选用及活动记录。

- [tests/studio_result_experience.test.mjs](../../../tests/studio_result_experience.test.mjs)
- [tests/studio_candidate_records.test.mjs](../../../tests/studio_candidate_records.test.mjs)
- [tests/studio_export_navigation.test.mjs](../../../tests/studio_export_navigation.test.mjs)
- [tests/result_experience_ui_fixture.py](../../../tests/result_experience_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/candidate-records.md](../../candidate-records.md)
- [docs/frontend/experience-phase3.md](../../frontend/experience-phase3.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。
