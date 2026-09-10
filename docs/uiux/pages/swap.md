# 参考视频换人

维护 ID：`swap`。关键词：换人、源视频、目标角色、对照审核。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>`，mode=swap。步骤键 source → edit → review → export，页面为源视频与角色、分段与替换、对照审核、成片。

## 保留优先

保留源表演/目标角色的明确区分、原片与结果对照、片段审核及成片入口；共享工作区位置是已有基础。

## 修改边界及联动

工作区由 app/workspace-controller.js 组装。分段准备、替换提示词预览和最终审核有不同职责；布局调整不能改变切段、接受候选或自动推进语义。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/features/source-preparation/index.js](../../../static/studio/features/source-preparation/index.js) | `createFeature` |
| [static/studio/features/swap-prompts/index.js](../../../static/studio/features/swap-prompts/index.js) | `createFeature` |
| [static/studio/features/swap-prompts/preview.js](../../../static/studio/features/swap-prompts/preview.js) | `createPromptPreview` |
| [static/studio/modes/swap/workspace.js](../../../static/studio/modes/swap/workspace.js) | `navigation`, `className`, `renderEdit`, `reviewComparison` |
| [static/studio/styles/modes.css](../../../static/studio/styles/modes.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/swap.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

来源与结果是否易区分；取消保存不开始制作；末段审核进入成片；参考与主画面都可读。

- [tests/studio_source_preparation.test.mjs](../../../tests/studio_source_preparation.test.mjs)
- [tests/studio_frontend.test.mjs](../../../tests/studio_frontend.test.mjs)
- [tests/result_experience_ui_fixture.py](../../../tests/result_experience_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/README.md](../../frontend/README.md)
- [docs/prompts/swap-template-v3.md](../../prompts/swap-template-v3.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

原片与结果对照保留，候选记录移至对照主区下方；实际运行记录、选用影响确认、入库和移除复用原事件。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。
