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

## R1布局接入（2026-09-10）

历史R1曾由全站左侧进入；最新已恢复顶部任务按钮及“更多”内回收站/存储入口，仍是原队列／三类回收／备份业务，不复制原型JSON替代真实导出。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 了解正在运行的任务，或恢复/管理本地内容。
- **第一眼最想看见什么？** 任务看所属项目与运行/异常；回收站看对象和来源；存储看位置/占用及操作影响。
- **最自然的动作：** 任务：查看 → 定位 → 停止/处理异常；回收：选类别 → 查找 → 核对 → 恢复；存储：查看 → 选择操作 → 核对范围 → 执行
- **空间判断：** 三个业务分别组织。任务是紧凑状态列表；回收按三类导航；存储突出操作范围与反馈，不机械复用创作工作区。
- **必须保留：** 准确任务归属停止、活动与历史分离、分类恢复、原备份保护。
- **直接验收场景：** 只用假任务/临时库；运行中、未知状态、空回收、父项未恢复均有准确动作和反馈。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。


## Q6b对象与恢复说明（2026-09-12）

任务确认区补项目名、任务名与短记录编号，所有类型均可在确认处辨认对象；原停止/取消/恢复接口不变。回收恢复按钮可访问名称包含对象与任务，确认说明包含任务归属；保留父项目未恢复保护与非级联恢复。

[管理上下文夹具](../../../tests/management_context_ui_fixture.py)使用真实临时API/库与假引擎。1366×768、430×900通过档案入口、已删除卡说明、恢复取消、父恢复保留已移除候选、单独恢复候选、停止取消零提交、按准确引擎任务地址停止，以及状态仍为running/停止已请求。7项Node任务/回收检查、2项后端精确停止/非级联恢复通过；原首页两档结构检查通过（1366×768、430×768）。未进入项目编辑器重测草稿，也未做真实引擎取消。

证据 `<本地维护路径>`：final为停止请求反馈，confirmation为再次打开但不提交的确认画面，宽窄均实际查看；home为首页结构保留检查。项目/任务信息与操作可读，纸色和原任务卡结构保留；窄屏确认内容正常纵向滚动。档案/回收主要通过DOM与真实API断言核对，不冒充全部画面视觉验收。checks保留首次夹具误将引擎按URL取消当作body.prompt_id取消的失败证据，按现有真实契约修正后通过。未生产重载、真实生成、提交或发布，最终体验待用户反馈。
