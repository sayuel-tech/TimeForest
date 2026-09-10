# 草稿、轮询、错误与反馈

维护 ID：`state`。关键词：草稿、刷新、轮询、保存、取消、报错、断线、计时、弹窗。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

公共状态基础，具体呈现优先转到 shell/settings/production 等专题。本专题的 ui 全目录匹配用于覆盖底层工具，不表示所有业务由此负责。

## 保留优先

保留草稿对象身份、迟到响应保护、局部状态更新、视图恢复、用户认可的紧凑计时模式。

## 修改边界及联动

core 是状态/调用机制，ui 是呈现。ProjectSession、ImageSession、接续与 creation 控制器边界不同，不能统一 CSS 时重建保存系统；request pending 与任务 running 分开。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/contracts/project-refresh.js](../../../static/studio/contracts/project-refresh.js) | `projectContent`, `mergeProjectRuntime`, `acceptProjectRevision` |
| [static/studio/contracts/project.js](../../../static/studio/contracts/project.js) | `authoredFields`, `normalizeProject`, `signature` |
| [static/studio/core/api-client.js](../../../static/studio/core/api-client.js) | `ApiError`, `api`, `readLegacyProject` |
| [static/studio/core/async-state.js](../../../static/studio/core/async-state.js) | `readStamp`, `uncertainMutation`, `requireKnownStatus`, `currentRead`, `canReplaceDraft` |
| [static/studio/core/capability-client.js](../../../static/studio/core/capability-client.js) | `visibleParameters`, `choicesFor`, `geometryPreview` |
| [static/studio/core/export-lifecycle.js](../../../static/studio/core/export-lifecycle.js) | `finishesReview`, `exportNavigation` |
| [static/studio/core/image-catalog.js](../../../static/studio/core/image-catalog.js) | `assertImageCatalog` |
| [static/studio/core/image-session.js](../../../static/studio/core/image-session.js) | `ImageSession` |
| [static/studio/core/progress-channel.js](../../../static/studio/core/progress-channel.js) | `watchProject` |
| [static/studio/core/project-commands.js](../../../static/studio/core/project-commands.js) | `ProjectCommands` |
| [static/studio/core/project-session.js](../../../static/studio/core/project-session.js) | `ProjectSession` |
| [static/studio/core/single-flight.js](../../../static/studio/core/single-flight.js) | `singleFlight` |
| [static/studio/core/snapshot-update.js](../../../static/studio/core/snapshot-update.js) | `sameSnapshot`, `snapshotChange` |
| [static/studio/core/source-target.js](../../../static/studio/core/source-target.js) | `sourceTarget` |
| [static/studio/core/task-state.js](../../../static/studio/core/task-state.js) | `TASK_STATES` |
| [static/studio/core/upload-client.js](../../../static/studio/core/upload-client.js) | `uploadForm`, `uploadAsset` |
| [static/studio/styles/components.css](../../../static/studio/styles/components.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-center.css](../../../static/studio/styles/task-center.css) | 文件入口 / 样式定义 |
| [static/studio/ui/asset-origin.js](../../../static/studio/ui/asset-origin.js) | `projectOriginLink`, `assetVersionLink`, `lineageMarkup`, `assetOriginMarkup` |
| [static/studio/ui/async-feedback.js](../../../static/studio/ui/async-feedback.js) | `asyncFeedback` |
| [static/studio/ui/candidate-records.js](../../../static/studio/ui/candidate-records.js) | `recordControl`, `removedRecords`, `recordConfirmation` |
| [static/studio/ui/choice-dialog.js](../../../static/studio/ui/choice-dialog.js) | `chooseAction`, `confirmLeave` |
| [static/studio/ui/creation-job-status.js](../../../static/studio/ui/creation-job-status.js) | `creationJobStatus` |
| [static/studio/ui/draft-status.js](../../../static/studio/ui/draft-status.js) | `draftStatus` |
| [static/studio/ui/empty-state.js](../../../static/studio/ui/empty-state.js) | `illustratedEmpty`, `bindDecorativeArt` |
| [static/studio/ui/error-feedback.js](../../../static/studio/ui/error-feedback.js) | `describeError`, `errorFeedback`, `bindErrorFeedback` |
| [static/studio/ui/input-inventory.js](../../../static/studio/ui/input-inventory.js) | `inputTable`, `inputActions`, `bindInputInventory` |
| [static/studio/ui/library-navigation.js](../../../static/studio/ui/library-navigation.js) | `libraryNavigation` |
| [static/studio/ui/media-player.js](../../../static/studio/ui/media-player.js) | `mediaPlayer`, `bindMediaPlayers` |
| [static/studio/ui/model-selector.js](../../../static/studio/ui/model-selector.js) | `modelSelector`, `bindModelSelectors` |
| [static/studio/ui/primitives.js](../../../static/studio/ui/primitives.js) | `esc`, `fmt`, `bytes`, `LABELS`, `status`, `opts`, `field` |
| [static/studio/ui/production-settings.js](../../../static/studio/ui/production-settings.js) | `openProductionSettings`, `parameterLoras`, `validateSettingsInputs`, `parameterGrid`, `parameterSlots`, `productionSettingsActions`, `productionGroups` |
| [static/studio/ui/prompt-editor.js](../../../static/studio/ui/prompt-editor.js) | `readingDisclosure`, `openReading`, `bindReadingPreviews`, `expandPrompt`, `promptTools` |
| [static/studio/ui/reference-assets.js](../../../static/studio/ui/reference-assets.js) | `importOptions`, `referenceAssetCard` |
| [static/studio/ui/reference-metadata.js](../../../static/studio/ui/reference-metadata.js) | `referencePurposes`, `needsSubject`, `referenceMetadata`, `chooseReferenceMetadata` |
| [static/studio/ui/result-view.js](../../../static/studio/ui/result-view.js) | `candidateState`, `candidateButton`, `resultActions`, `collectionActions` |
| [static/studio/ui/run-timing.js](../../../static/studio/ui/run-timing.js) | `runTiming`, `runStatusRow` |
| [static/studio/ui/source-navigation.js](../../../static/studio/ui/source-navigation.js) | `showSourceNavigation` |
| [static/studio/ui/source-parameters.js](../../../static/studio/ui/source-parameters.js) | `sourceParametersMarkup` |
| [static/studio/ui/status-region.js](../../../static/studio/ui/status-region.js) | `updateStatusRegion` |
| [static/studio/ui/workbench.js](../../../static/studio/ui/workbench.js) | `workbench`, `propertyTabs`, `bindWorkbench`, `fitWorkbench` |
| [static/studio/ui/workspace-actions.js](../../../static/studio/ui/workspace-actions.js) | `workspaceActionGroups`, `workspaceActions` |
| [static/studio/ui/workspace-chrome.js](../../../static/studio/ui/workspace-chrome.js) | `workspaceHeader`, `workspaceSteps`, `bindWorkspaceSteps` |
| [static/studio/ui/workspace-view-state.js](../../../static/studio/ui/workspace-view-state.js) | `workspaceViewState` |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/state.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

轮询后输入仍保存；失败不清正文；弹窗关闭焦点回位；隐藏页暂停读取但不终止后台任务；进度不用虚构数值。

- [tests/studio_async_experience.test.mjs](../../../tests/studio_async_experience.test.mjs)
- [tests/studio_refresh_policy.test.mjs](../../../tests/studio_refresh_policy.test.mjs)
- [tests/studio_run_timing.test.mjs](../../../tests/studio_run_timing.test.mjs)
- [tests/async_experience_ui_fixture.py](../../../tests/async_experience_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/refresh-and-libraries.md](../../frontend/refresh-and-libraries.md)
- [docs/frontend/experience-phase4.md](../../frontend/experience-phase4.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。


## 本轮接入

电影时间码保留按对象隔离的显示草稿；非法输入经原save门拒绝，报错重绘不丢输入。资产类别筛选仅改视图。 具体职责与证据见 [R1接入](../site-experience.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。
