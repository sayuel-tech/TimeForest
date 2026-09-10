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
