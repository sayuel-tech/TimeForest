# 电影创作

**v6.3.33 功能状态：剧本创作模式和电影创作模式目前不可用。** 本版保留开发中的页面与代码，尚未完成可用性与完整创作流程验收；请勿将这两个模式视为已交付功能。后续状态以版本说明为准。

维护 ID：`movie`。关键词：电影、片段生成、剪辑拼接、剧本返回。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>`，kind=movie。片段生成 → 剪辑拼接；采用剧本来源和生成片段，不复制一个完整剧本编辑器。

## 保留优先

保留纵向分镜/片段关系、横向编排、源剧本返回以及已生成候选/剪辑保护；既有候选空态水彩可沿用。

## 修改边界及联动

共同目录在 shot-segment-tree，公共状态/参数/Prompt 来源不属于 mode 私有代码。同步剧本、采用候选、剪辑顺序分别是业务动作，不能用视觉重排代替真实数据同步。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/modes/movie/workspace.js](../../../static/studio/modes/movie/workspace.js) | `mountWorkspace` |
| [static/studio/styles/creation.css](../../../static/studio/styles/creation.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/movie.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

生成前对象与来源明确；回到父分镜和返回电影位置；同步前后选用/剪辑保留；空态与有候选状态分开。

- [tests/creation_return_context.test.mjs](../../../tests/creation_return_context.test.mjs)
- [tests/creation_ui_fixture.py](../../../tests/creation_ui_fixture.py)
- [tests/test_creation_movie.py](../../../tests/test_creation_movie.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/creation-modes.md](../../creation-modes.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。
