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
