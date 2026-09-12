# 参考图长视频

维护 ID：`image_story`。关键词：参考图长视频、角色与片段、图文分镜。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>`，mode=image_story。edit 角色与片段 → review 制作与审核 → export 成片。

## 保留优先

保留分镜正文与当前参考图关联、审核中本段参考及上一段检查入口。

## 修改边界及联动

模式只提供 renderEdit/reviewComparison/navigation 等适配，共用 controller、prompts、production 和 export。asset_mode 的沿用/自定义/不使用是有效输入规则，不能仅改文案或隐藏选择。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/modes/image-story/workspace.js](../../../static/studio/modes/image-story/workspace.js) | `navigation`, `className`, `renderEdit`, `reviewComparison` |
| [static/studio/styles/modes.css](../../../static/studio/styles/modes.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/image_story.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

长正文、参考集、切换分镜、none 与继承状态、审核对照；公共正文改动同时核对文生和换人。

- [tests/studio_asset_modes.test.mjs](../../../tests/studio_asset_modes.test.mjs)
- [tests/studio_frontend.test.mjs](../../../tests/studio_frontend.test.mjs)
- [tests/readability_ui_fixture.py](../../../tests/readability_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/parameter-map.md](../../frontend/parameter-map.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

公共目录与参考区接入；审核候选记录移至主区，原参考绑定、依赖失效、分段和导出不变。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 从已有角色、场景和风格素材发展连续视频。
- **第一眼最想看见什么？** 当前片段的内容和实际参考；审核时先看当前结果。
- **最自然的动作：** 添加参考 → 写各段内容 → 生成 → 挑选/重做 → 合成导出
- **空间判断：** 编辑时正文居中占主空间、片段目录辅助定位、参考在旁；审核时主媒体优先。布局可以随阶段改变。
- **必须保留：** asset_mode沿用/自定义/不使用、固定素材版本、上段参考和审核。
- **直接验收场景：** 切段后正文与参考不串位；长正文可读；选择素材取消及保存失败不推进。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。

## Q4b正文与实际参考（2026-09-10）

编辑区原重复缩略改为可展开的当前片段参考摘要，默认把空间留给正文；侧栏仍保留素材选择、管理和固定引用。摘要与审核都使用原localAssets解析，显示P编号、引用方式和图片数量；审核图片补可见名称。不使用素材的提示只说明引用关闭，避免把新场景误称为承接上一段。原上段视频、结果播放器、候选动作和生成参数保留。

复用reading-disclosure与workspaceViewState的对象键，展开不写项目；样式只匹配本页参考摘要和image-review图注，沿用公共纸色、字体和阅读变量，不修改全局尺度。1366×768编辑正文可见约8行，430×900约6行，可滚动读到全文结尾；审核仍以媒体为主，窄屏参考顺排在媒体下。首页历史截图只作纸色、字重和柔和边界参照，本页当前四张截图已查看；合成素材不代表真实人物辨认效果。窄屏原目录/侧栏工具文字仍紧凑，本次未改公共壳层。

直接检查：tests/image_story_layout_ui_fixture.py，受控API、两个不同片段、600字以上正文、现有插画与合成视频，四场景覆盖切段不串草稿、auto/custom/none、展开保留输入、保存冲突不推进、恢复保存及零生成。tests/studio_asset_modes.test.mjs三项通过；既有result_experience_ui_fixture.py仅image_story两档通过，覆盖播放/暂停/定位/错误重试、入库不选用、移除恢复与原确认语义。模拟保存不冒充真实生产API验收，未真实上传、模型调用或生产重载。

证据：<本地维护路径>。撤回按本批diff合并，保留后续编辑；不回退配置、数据、媒体或baseline标签。最终操作感待用户反馈，当前批次与下一步只见维护基线。
