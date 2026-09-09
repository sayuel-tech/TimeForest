# 任务、回收站和本地管理

维护 ID：`management`。关键词：任务中心、任务列表、回收站、本地存储、备份、分类与合集。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

全局 #global-tasks 按钮；库内 #/assets?view=tasks/storage/organize/trash。资产处理任务与生成任务不同。

## 保留优先

保留准确对象停止、活动与历史分开、三类回收站与原恢复机制；不可借整理入口删除历史或文件。

## 修改边界及联动

任务事实来自 h3ui/task_center.py；回收站来自 studio_recycle 与库原标记；存储/备份存在真实写操作，索引盘点不执行这些动作。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/features/task-center/index.js](../../../static/studio/features/task-center/index.js) | `confirmation`, `visibleTasks`, `taskCard`, `mountTaskCenter` |
| [static/studio/pages/asset-library/engine-settings.js](../../../static/studio/pages/asset-library/engine-settings.js) | `openLauncher` |
| [static/studio/pages/asset-library/index.js](../../../static/studio/pages/asset-library/index.js) | `mountLibrary` |
| [static/studio/pages/asset-library/recycle-bin.js](../../../static/studio/pages/asset-library/recycle-bin.js) | `recycleCategories`, `recycleUrl`, `restoreRequest`, `recycleView`, `mountRecycleBin` |
| [static/studio/styles/library.css](../../../static/studio/styles/library.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-center.css](../../../static/studio/styles/task-center.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/management.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

排队/运行/未知状态可辨，停止请求不冒充已停止；错误保留处理入口；父项目恢复不级联复活已移除候选。

- [tests/task_center_ui_fixture.py](../../../tests/task_center_ui_fixture.py)
- [tests/studio_task_center.test.mjs](../../../tests/studio_task_center.test.mjs)
- [tests/studio_recycle_bin.test.mjs](../../../tests/studio_recycle_bin.test.mjs)
- [tests/test_recycle_bin.py](../../../tests/test_recycle_bin.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/task-queue.md](../../task-queue.md)
- [docs/recycle-bin.md](../../recycle-bin.md)
- [docs/director-launcher.md](../../director-launcher.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。
