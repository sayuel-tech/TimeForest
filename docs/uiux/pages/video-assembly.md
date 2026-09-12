# 视频接续

维护 ID：`video_assembly`。关键词：视频接续、续写、轨道、拼接、添加视频。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>`，kind=assembly、mode=video_assembly。视频与排序 → 续接与挑选 → 成片。

## 保留优先

保留原片/成功续接独立轨道、明确选用、来源参数，以及非第一步原地添加视频。历史续接页截图已查看。

## 修改边界及联动

track.js 管显示和排序，workspace.js 管当前对象/保存与生成协调，references/settings 各自适配。轨道排序不能重写生成依赖；纯拼接与 AI 续接不能混成同一执行前提。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/modes/video-assembly/import-dialog.js](../../../static/studio/modes/video-assembly/import-dialog.js) | `chooseVideoImport` |
| [static/studio/modes/video-assembly/references.js](../../../static/studio/modes/video-assembly/references.js) | `boundReferences`, `referencePanels`, `bindReferences` |
| [static/studio/modes/video-assembly/settings.js](../../../static/studio/modes/video-assembly/settings.js) | `visibleParameters`, `resetParameters`, `switchRecipe`, `settingsDialog` |
| [static/studio/modes/video-assembly/source-parameters.js](../../../static/studio/modes/video-assembly/source-parameters.js) | 文件入口 / 样式定义 |
| [static/studio/modes/video-assembly/track.js](../../../static/studio/modes/video-assembly/track.js) | `trackItems`, `moveTrack` |
| [static/studio/modes/video-assembly/workspace.js](../../../static/studio/modes/video-assembly/workspace.js) | `activeClips`, `savePayload`, `moveClip`, `mountWorkspace` |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/video-assembly.css](../../../static/studio/styles/video-assembly.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/video_assembly.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

追加视频不强制回第一步；改候选保留槽位；返回恢复；保存与轮询冲突；导出顺序与轨道相同。

- [tests/studio_video_assembly.test.mjs](../../../tests/studio_video_assembly.test.mjs)
- [tests/video_assembly_track_ui_fixture.py](../../../tests/video_assembly_track_ui_fixture.py)
- [tests/video_assembly_draft_ui_fixture.py](../../../tests/video_assembly_draft_ui_fixture.py)
- [tests/assembly_import_ui_fixture.py](../../../tests/assembly_import_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/video-assembly.md](../../video-assembly.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

原轨道、续写与普通拼接保留，接入公共导航、底栏和按需参考抽屉，不改变track_order和固定声画尾部。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 沿视频结尾续接，并把已有与新增片段组织成片。
- **第一眼最想看见什么？** 视频目录的成片顺序、选中片段、从哪里继续。
- **最自然的动作：** 添加视频 → 选接续位置并描述 → 生成选用 → 排序 → 拼接导出
- **空间判断：** 目录表达轨道顺序，主区展示当前视频/接续；材料与来源辅助。不能把生成依赖和导出顺序混为一谈。
- **必须保留：** track_order、继续沿已生成片段接续、固定来源、选用幂等和原片保存。
- **直接验收场景：** 选用后轨道新增、再续接、排序与导出输入一致；不调用真实ComfyUI。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。


## Q5b接续身份与成片摘要（2026-09-12）

保留纸色、原视频目录、主区续写描述/播放器、参考侧栏及原选用操作；本批差异是当前续写、接续起点与查看/选用身份缺少直接说明。现主标题补续写编号，明确下一次接续使用原片终点或前段已选结果；轨道排序只改变成片顺序。候选播放器前说明正在查看与已选用编号，成片页显示轨道片段数、总时长及按列表顺序拼接。

未改track_order、生成依赖、固定运行快照、选用槽位与移除保护。接续起点描述的是下一次生成所用来源，不替代历史候选的固定来源记录。

新增 [接续上下文夹具](../../../tests/assembly_context_ui_fixture.py)，使用真实临时API、合成媒体与假导出末端。1366×768、430×900通过：选用只追加一次、排序落盘与重载、排序不改接续起点、沿已选结果新增续写的真实服务来源、未选续写不进轨道、导出快照与轨道一致、身份与片段摘要、媒体加载和无横向溢出。新增但未选续写触发原导出保护，夹具移除该测试段后导出；未改此保护。另6项Node轨道/参数检查和2项后端来源/选用检查通过。

证据 `<本地维护路径>`：final为视频与排序步骤，identity为续接与挑选步骤，两档均实际查看；续接起点/编号可读，窄屏正常换行，候选身份在下方滚动区，导出摘要由DOM断言检查。夹具挂载工作区组件，未含全站顶部导航，不能当作完整生产外壳验收。假导出文件用于完成状态与快照验证，其时长不代表真实拼接输出。未真实模型、生产重载、提交或发布，最终体验仍待用户反馈。
