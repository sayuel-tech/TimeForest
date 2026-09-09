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
