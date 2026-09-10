# 文生视频

维护 ID：`text_story`。关键词：文生视频、剧本与镜头、画面与剧本审核。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>`，mode=text_story。edit 剧本与镜头 → review 画面与剧本审核 → export 成片。

## 保留优先

保留镜头目录、正文优先、成片/原文对照以及按需参考。这里与新剧本创作 mode=authoring 是不同入口。

## 修改边界及联动

复用前三视频的会话、字段、审核和导出。不能把文字输入改造成强制先调用 LLM；声音、结束状态等字段仍须按原参数契约保存。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/modes/text-story/workspace.js](../../../static/studio/modes/text-story/workspace.js) | `navigation`, `className`, `renderEdit`, `reviewComparison` |
| [static/studio/styles/modes.css](../../../static/studio/styles/modes.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/text_story.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

正文编辑与长文阅读、切镜头恢复、原文与候选比较、保存失败保护。

- [tests/studio_frontend.test.mjs](../../../tests/studio_frontend.test.mjs)
- [tests/studio_asset_modes.test.mjs](../../../tests/studio_asset_modes.test.mjs)
- [tests/readability_ui_fixture.py](../../../tests/readability_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/parameter-map.md](../../frontend/parameter-map.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

公共写作与审核区接入；候选位于主区，原Prompt字段、声音、保存和生成门不变。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。
