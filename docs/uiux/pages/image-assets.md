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

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 创作或修改图片，反复筛选得到可复用资产。
- **第一眼最想看见什么？** 编辑阶段看画布和当前工具；挑选阶段看所选图片。
- **最自然的动作：** 选工具/输入 → 描述或编辑 → 生成 → 对比筛选/重做 → 保存入库
- **空间判断：** 画布是空间中心，工具围绕画布；结果阶段候选索引紧凑，主图可完整查看。参数仅一个公共入口。
- **必须保留：** 五工具、遮罩/扩边、独立任务、候选、种子、入库去重。
- **直接验收场景：** 真实指针与遮罩保存只做临时fixture；参数取消不重建画布；选用与入库分开。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。

## Q5a画布、候选与入库（2026-09-12）

保留五工具、原画布/笔刷/扩边、任务级草稿、计时和公共结果动作。挑选与使用页主图前显示正在查看与实际选定的候选编号，两者从同一任务实际outputs解析，与现有候选列表编号一致；编号随原返回顺序，不另造持久身份。主图与结果动作前置，候选列表及历史放后，主图按视口提供明确高度并完整适应图像，避免列表挤占后仅剩160px。仍允许在工作区滚动查找候选，不缩小素材或正文。窄屏公共目录工具栏对图片编辑工具行预留实际高度，避免覆盖扩图按钮；原Q4c规则已同时作用于图片结果页的shot-heading，本批补查并修正其文档范围。

直接检查：真实临时图片API、临时库与合成图片；1366×768/430×900画布两例通过真实指针标注、撤销/重做、参数取消保持同一canvas及未保存标注、不上传/保存、遮罩落盘、扩边96px与任务隔离，engine_attempts为空。候选同样两档通过查看/实际选定身份、主图先于列表、完整图像高度、原图对比开合、入库不选用不跳步骤、移除恢复及选用另一个候选。15项Node交互/计时与2项真实后端入库/去重检查通过。

证据<本地维护路径>；较早results保留测试错误，layout-final/results-priority为布局迭代，不当成交付截图。测试曾硬编码恢复后的编号，已改为以实际ID和列表顺序核对。结果夹具补空的提示词待收录响应，避免测试缺接口横幅挤占画面；此响应不证明提示词库业务。四张最终截图已查看，纸色/字体/边界保持，主图可辨、目录不遮挡，候选需正常滚动；合成图不代表真实素材质量或用户最终审美认可。

没有更改生成参数、后端数据语义、原图或运行记录；未生产重载、真实生成、提交或发布。恢复使用本批before/after差异，before含Q4b/Q4c，不能整体覆盖旧HEAD。AGENTS及PROJECT_GUIDE的图片控制器/画布/结果归属仍准确，无需新路由。当前下一批只见维护基线。

## 多图编辑（2026-09-12）

原双图工具显示为“多图编辑”，默认 A/B，右侧素材沿用原卡片和上传／资产选择，可增加到 I；额外位置可移除且不重编号，空位不参与生成。保留纸色、画布、参数单一入口、步骤与候选操作。新字段接入原任务保存及运行来源；未新建模式或结果动作。

体验准入：assetSelection/assetOrigins/assetUsage 复用原固定版本选择、来源链接与保存后登记；assetLifecycle 移除当前引用，保留文件和库；async/transfers 使用原 action/session/request 上传与错误机制；taskStates 保留占用保护；results/playback 未改。参数作用域仍为当前任务，取消参数不触及输入和画布。编译与多图扩展只消费已选图片，不拼贴或静默丢弃。

直接检查：tests/image_multiref_ui_fixture.py 在1366×768、430×900经真实临时图片API完成默认两图、7次上传、九图上限、保存、取消移除不变revision、移除C保留D、空位保存与重开、无横向溢出；engine_attempts均为空。两张截图已查看，保持画布及右侧滚动素材卡，窄屏使用原属性抽屉。tests/test_image_multiref.py验证九图执行快照、不可变旧运行、稀疏图编号、跨项目校验、原双图编译、节点缺失不提交，以及替身编码／VAE引用列表。21项原图片后端测试和15项Node交互／计时回归通过。

证据与恢复点：<本地维护路径>。配套节点在仓库comfyui_nodes，未安装到生产ComfyUI、未重启、未真实生成或发布；实际多图效果和资源占用未验收。当前状态见维护基线。
