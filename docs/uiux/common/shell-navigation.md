# 全局壳层、导航与空间

维护 ID：`shell`。关键词：页头、底栏、导航、三栏、侧栏、属性、步骤、响应式。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

全局壳层 → 路由 → 模式控制器 → workspaceHeader/workspaceSteps/workbench/workspaceActions。

## 保留优先

保留同任务的共同布局规律与属性开关的草稿保护；不因公共容器存在就强制每页三栏。

## 修改边界及联动

全局 header 在 static/index.html，项目 header 在 workspace-chrome，rail/canvas/inspector 在 workbench，底栏在 workspace-actions。CSS 还受 task-layouts 最后导入影响。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/index.html](../../../static/index.html) | 文件入口 / 样式定义 |
| [static/studio/app.js](../../../static/studio/app.js) | 文件入口 / 样式定义 |
| [static/studio/app/bootstrap.js](../../../static/studio/app/bootstrap.js) | 文件入口 / 样式定义 |
| [static/studio/app/mode-registry.js](../../../static/studio/app/mode-registry.js) | `setCreationEnabled`, `setAssemblyEnabled`, `setImageAssetsEnabled`, `registerMode`, `listModes`, `getMode` |
| [static/studio/styles/shell.css](../../../static/studio/styles/shell.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |
| [static/studio/ui/workbench.js](../../../static/studio/ui/workbench.js) | `workbench`, `propertyTabs`, `bindWorkbench`, `fitWorkbench` |
| [static/studio/ui/workspace-actions.js](../../../static/studio/ui/workspace-actions.js) | `workspaceActionGroups`, `workspaceActions` |
| [static/studio/ui/workspace-chrome.js](../../../static/studio/ui/workspace-chrome.js) | `workspaceHeader`, `workspaceSteps`, `bindWorkspaceSteps` |
| [static/studio/ui/workspace-view-state.js](../../../static/studio/ui/workspace-view-state.js) | `workspaceViewState` |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/shell.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

三层导航含义、返回位置、当前对象、辅助栏折叠、键盘步骤移动、固定底栏与正文末尾。

- [tests/workspace_navigation_ui_fixture.py](../../../tests/workspace_navigation_ui_fixture.py)
- [tests/studio_export_navigation.test.mjs](../../../tests/studio_export_navigation.test.mjs)
- [tests/creation_return_context.test.mjs](../../../tests/creation_return_context.test.mjs)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/shared-ui.md](../../frontend/shared-ui.md)
- [docs/frontend/visual-design-standard-v2.md](../../frontend/visual-design-standard-v2.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。


## 本轮接入

全站导航和连接状态已按最新反馈回到顶部，不再使用左侧全站栏或重复普通页顶栏。site-navigation测量实际顶栏高度，workbench据此保留正文及底栏空间；公共工作区步骤与底栏保留。窄屏目录／参考抽屉统一管理关闭、焦点及背景inert。 具体职责与证据见 [R1接入](../site-experience.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。
