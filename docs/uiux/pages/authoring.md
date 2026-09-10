# 剧本创作

**v6.3.34 功能状态：剧本创作模式和电影创作模式目前不可用。** 本版保留开发中的页面与代码，尚未完成可用性与完整创作流程验收；请勿将这两个模式视为已交付功能。后续状态以版本说明为准。

维护 ID：`authoring`。关键词：剧本、资产落实、资产绑定、分镜、片段Prompt、沟通、完整资产剧本。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>?step=0..4`：故事起点、剧本创作、资产落实、分镜设计、片段 Prompt。数字是零基步骤。对象定位还须读 shot-segment-tree/return-context。

## 保留优先

保留五页、跨页目录、对象隔离沟通和同一输出确认、全剧/分镜/片段真实资产作用域。用户要求第三页保留左目录、上资产下剧本。

## 修改边界及联动

现有资产需求已接入具名媒体网格、类别/待落实筛选和主操作/更多配置，资产区旧固定内滚动已移除；这些旧问题不再作为未实施任务。当前卡片密度已按后续反馈调整，最终业务可读性与整体体验仍待用户确认。后续按具体反馈维护 binding-cards.js 与 creation.css，不重写后端绑定解析；h3ui/creation/bindings.py 仍是有效资产解释入口。具体实现及历史问题见 site-experience 与 audit/findings。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/features/authoring-assist/binding-cards.js](../../../static/studio/features/authoring-assist/binding-cards.js) | `resolveBindings`, `mountBindingCards` |
| [static/studio/features/authoring-assist/conversation.js](../../../static/studio/features/authoring-assist/conversation.js) | `writingScope`, `conversationKey`, `scopedJobs` |
| [static/studio/features/authoring-assist/create-project.js](../../../static/studio/features/authoring-assist/create-project.js) | `createCreationProject` |
| [static/studio/features/authoring-assist/image-handoffs.js](../../../static/studio/features/authoring-assist/image-handoffs.js) | `mountImageHandoffs` |
| [static/studio/features/authoring-assist/index.js](../../../static/studio/features/authoring-assist/index.js) | `updateAssistStatus`, `mountAssist`, `bodyText` |
| [static/studio/features/authoring-assist/output-editor.js](../../../static/studio/features/authoring-assist/output-editor.js) | `structuredOutput`, `bindStructuredOutput` |
| [static/studio/features/authoring-assist/prompt-fields.js](../../../static/studio/features/authoring-assist/prompt-fields.js) | `promptFields`, `profileMarkup`, `promptMarkup`, `bindAuthoringPromptTools` |
| [static/studio/features/authoring-assist/references.js](../../../static/studio/features/authoring-assist/references.js) | `mountReferences` |
| [static/studio/features/shot-segment-tree/edit-preview.js](../../../static/studio/features/shot-segment-tree/edit-preview.js) | `previewEdit` |
| [static/studio/features/shot-segment-tree/index.js](../../../static/studio/features/shot-segment-tree/index.js) | `shotSegmentTree` |
| [static/studio/features/shot-segment-tree/return-context.js](../../../static/studio/features/shot-segment-tree/return-context.js) | `readReturnContext`, `returnHref`, `withReturnContext` |
| [static/studio/modes/authoring/workspace.js](../../../static/studio/modes/authoring/workspace.js) | `mountWorkspace` |
| [static/studio/styles/creation.css](../../../static/studio/styles/creation.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/authoring.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

具名缺口可识别；无需求不能伪造卡片；编辑/确认保留身份；全剧覆盖来源准确；图片补充后返回正确对象。

- [tests/creation_return_context.test.mjs](../../../tests/creation_return_context.test.mjs)
- [tests/creation_experience_ui_fixture.py](../../../tests/creation_experience_ui_fixture.py)
- [tests/test_creation_experience.py](../../../tests/test_creation_experience.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/creation-experience-implementation.md](../../frontend/creation-experience-implementation.md)
- [docs/product/creation-experience-correction.md](../../product/creation-experience-correction.md)
- [docs/creation-modes.md](../../creation-modes.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

资产需求已改为具名媒体网格及主／次操作；筛选按对象保留而不保存项目。上资产下完整资产剧本；五页目录和真实绑定、局部覆盖、同一输出编辑保留。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。
