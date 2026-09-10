# 图片资产创作

维护 ID：`image_assets`。关键词：图片、画布、文生图、局部重绘、扩图、图片任务。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>`，kind=image。编辑/描述与创作 → 生成与挑选 → 保存与使用；文字分支与单图、双图、局部、扩图共五工具。

## 保留优先

保留画布、任务级草稿、五工具与候选流；图片计时呈现为 AGENTS 明确记录的用户认可项。文生图历史截图已查看，未称本轮全工具体验验收。

## 修改边界及联动

控制器组合 ImageSession、ImageCanvas 与 workspace-view；图片参数见 settings 索引。更换布局不能重新上传遮罩、丢掉几何状态或将候选选择当作新底图。跨工具仍按原任务边界。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/app/image-workspace-controller.js](../../../static/studio/app/image-workspace-controller.js) | `mountWorkspace` |
| [static/studio/features/image-canvas/index.js](../../../static/studio/features/image-canvas/index.js) | `ImageCanvas` |
| [static/studio/features/image-results/transfer.js](../../../static/studio/features/image-results/transfer.js) | `sendToVideo` |
| [static/studio/features/image-results/workspace-view.js](../../../static/studio/features/image-results/workspace-view.js) | `imageSteps`, `imageRunStates`, `chosenOutput`, `generationReason`, `taskStatus`, `imageActionBar`, `imageRecordHistory` |
| [static/studio/styles/image-assets.css](../../../static/studio/styles/image-assets.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/image_assets.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

输入/画布取消无副作用，刷新不污染当前输入；再生成与继续编辑分清；入库不自动选用；窄窗主编辑区可用。

- [tests/studio_image_interactions.test.mjs](../../../tests/studio_image_interactions.test.mjs)
- [tests/studio_image_clock.test.mjs](../../../tests/studio_image_clock.test.mjs)
- [tests/image_parameter_ui_fixture.py](../../../tests/image_parameter_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/image-assets.md](../../image-assets.md)
- [docs/frontend/image-workspace-ui.md](../../frontend/image-workspace-ui.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

原画布／遮罩／工具与候选保留，接入公共抽屉和步骤；窄屏不自动遮挡画布。真实鼠标遮罩与扩边保存见专用fixture。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。
