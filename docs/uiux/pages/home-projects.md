# 首页与项目档案

维护 ID：`home`。关键词：首页、项目档案、新建、继续创作。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/` 首页；`#/archive` 档案；新建进入 `#/p/<id>`。模式注册有七项，实际展示受后台能力开关控制。

## 保留优先

保留首页独立模式水彩插画、项目名称/状态与继续入口。首页美术历史样例已查看，具体每个页面的用户认可程度不作扩大推断。

## 修改边界及联动

新建由 bootstrap 协调；剧本/电影另走 authoring-assist/create-project。档案中的旧项目读取与恢复是兼容业务，不能在页面整理时删除。全局任务是按钮打开的对话框，不是新路由。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/app/bootstrap.js](../../../static/studio/app/bootstrap.js) | 文件入口 / 样式定义 |
| [static/studio/app/mode-registry.js](../../../static/studio/app/mode-registry.js) | `setCreationEnabled`, `setAssemblyEnabled`, `setImageAssetsEnabled`, `registerMode`, `listModes`, `getMode` |
| [static/studio/pages/archive.js](../../../static/studio/pages/archive.js) | `createFeature` |
| [static/studio/pages/home.js](../../../static/studio/pages/home.js) | `projectCard`, `renderHome` |
| [static/studio/styles/modes.css](../../../static/studio/styles/modes.css) | 文件入口 / 样式定义 |
| [static/studio/styles/shell.css](../../../static/studio/styles/shell.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/home.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

检查新建取消、旧项目继续、模式隐藏时旧项目提示、回到档案后的查找；不通过生产项目创建操作取证。

- [tests/site_layout_ui_fixture.py](../../../tests/site_layout_ui_fixture.py)
- [tests/readability_ui_fixture.py](../../../tests/readability_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/project-archive-deletion.md](../../project-archive-deletion.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## 最新首页恢复（2026-09-10）

用户已退回R1的最近项目优先首页，恢复原版森林主视觉、创作方式、最近项目的顺序，保留原插画及窄屏主视觉。renderHome复用接入前模板，项目卡仍使用当前真实类型摘要；hero-start只滚动到创作方式，不改变路由或创建项目。首页不使用工作区专属tf-experience皮肤。全站导航与状态恢复顶部，普通页不叠加第二个页头。当前状态及检查见[本次接入](../site-experience.md)。

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 首页选择创作方式；项目档案继续已有工作。
- **第一眼最想看见什么？** 首页森林主视觉与清楚的模式入口；档案看项目名称、类型、进度与最近状态。
- **最自然的动作：** 选择方式/找到项目 → 新建或进入 → 开始/继续工作
- **空间判断：** 保留原版森林首页和顶部全站导航；档案以可扫描列表/卡片定位项目，不改成首页大幅最近作品。
- **必须保留：** 原模式入口、项目状态、删除恢复与离开保护。
- **直接验收场景：** 原版首页布局明确保留；项目卡状态清楚，进入后定位和草稿保护正确。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。


## Q6b对象与恢复说明（2026-09-12）

档案已删除卡原为不可跳转article，却仍显示“继续制作”。projectCard增加可选deleted呈现，档案显示“恢复后可继续制作”；首页默认调用与原森林主视觉/模式/最近项目顺序不变。恢复后继续入口指向同一原项目。

[管理上下文夹具](../../../tests/management_context_ui_fixture.py)使用真实临时API/库与假引擎。1366×768、430×900通过档案入口、已删除卡说明、恢复取消、父恢复保留已移除候选、单独恢复候选、停止取消零提交、按准确引擎任务地址停止，以及状态仍为running/停止已请求。7项Node任务/回收检查、2项后端精确停止/非级联恢复通过；原首页两档结构检查通过（1366×768、430×768）。未进入项目编辑器重测草稿，也未做真实引擎取消。

证据 `<本地维护路径>`：final为停止请求反馈，confirmation为再次打开但不提交的确认画面，宽窄均实际查看；home为首页结构保留检查。项目/任务信息与操作可读，纸色和原任务卡结构保留；窄屏确认内容正常纵向滚动。档案/回收主要通过DOM与真实API断言核对，不冒充全部画面视觉验收。checks保留首次夹具误将引擎按URL取消当作body.prompt_id取消的失败证据，按现有真实契约修正后通过。未生产重载、真实生成、提交或发布，最终体验待用户反馈。
