# 提示词库与全文阅读

维护 ID：`prompts`。关键词：提示词库、全文、查找、收藏Prompt、自动收录。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/prompts` 全局管理；项目内通过公共工具栏调用浏览器/编辑器。

## 保留优先

保留同一会话的列表/全文切换、用途与模型分类、固定版本和保存后收录。历史列表截图已查看，不能将其替换为永久挤压全文的三栏。

## 修改边界及联动

page index 只是挂载；browser/editor/adapters/collection/records 是不同职责。ui/prompt-editor 提供通用阅读，不等于整个提示词库。应用改草稿，收藏与保存/生成分别处理。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/features/prompt-library/adapters.js](../../../static/studio/features/prompt-library/adapters.js) | `bindVideoPrompts`, `bindImagePrompts`, `bindAssemblyPrompts` |
| [static/studio/features/prompt-library/api.js](../../../static/studio/features/prompt-library/api.js) | `promptApi`, `promptCatalog` |
| [static/studio/features/prompt-library/browser.js](../../../static/studio/features/prompt-library/browser.js) | `mountPromptBrowser` |
| [static/studio/features/prompt-library/collection.js](../../../static/studio/features/prompt-library/collection.js) | `promptCollectionNotice` |
| [static/studio/features/prompt-library/editor.js](../../../static/studio/features/prompt-library/editor.js) | `closePromptEditor`, `contentText`, `fieldNames`, `openEditor`, `editBranch` |
| [static/studio/features/prompt-library/records.js](../../../static/studio/features/prompt-library/records.js) | `recordSource`, `addRecordButton`, `showRecords` |
| [static/studio/features/prompt-library/tools.js](../../../static/studio/features/prompt-library/tools.js) | `pickPrompt`, `bindPromptEditor` |
| [static/studio/pages/prompt-library/index.js](../../../static/studio/pages/prompt-library/index.js) | `mountPromptLibrary` |
| [static/studio/styles/collection-navigation.css](../../../static/studio/styles/collection-navigation.css) | 文件入口 / 样式定义 |
| [static/studio/styles/prompt-library.css](../../../static/studio/styles/prompt-library.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/ui/prompt-editor.js](../../../static/studio/ui/prompt-editor.js) | `readingDisclosure`, `openReading`, `bindReadingPreviews`, `expandPrompt`, `promptTools` |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/prompts.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

读长文后返回列表位置；取消不应用；保存成功后收录且不重复；当前文字与运行时文字区分。

- [tests/prompt_library_ui_fixture.py](../../../tests/prompt_library_ui_fixture.py)
- [tests/test_prompt_library.py](../../../tests/test_prompt_library.py)
- [tests/readability_ui_fixture.py](../../../tests/readability_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/prompt-library.md](../../prompt-library.md)
- [docs/frontend/readability-implementation.md](../../frontend/readability-implementation.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

保留原用途／家族分类、全文读写和固定版本，接入共同导航与管理布局，未引入原型模拟存储。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 找到适用文字，阅读并复用或调整。
- **第一眼最想看见什么？** 用途/模型分支位置、候选摘要、可阅读的完整正文。
- **最自然的动作：** 按用途查找 → 阅读全文 → 选版本/编辑 → 应用
- **空间判断：** 摘要用于查找，全文必须获得充分宽高；窄屏允许列表/全文切换并保留返回位置，不能机械压成三栏。
- **必须保留：** 保存项目自动收录、家族分类、版本与来源、应用不自动生成。
- **直接验收场景：** 长中文/英文、空结果、有结果及返回列表；应用前后目标字段与取消语义一致。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。


## Q6a查找与版本选择（2026-09-12）

保留用途/模型分类与同会话列表/全文切换，不改成长驻三栏。搜索或筛选无匹配时说明调整条件，真正空分类与回收站分别提示；选择器空分类提示切换用途/模型或全库查找。当前选择按钮标明版本号，历史版本沿原接口选择；未改正文、应用草稿、保存或自动收录。

新增 [两库选择上下文夹具](../../../tests/library_selection_context_ui_fixture.py)，真实临时库/API与现有站内插画，禁止生成引擎访问。两库选择1366×768、430×900四场景通过：空搜索恢复、长名称和全文、返回保留筛选、取消返回null、资产固定版本、提示词历史版本1与当前版本2区分；资产多选勾选与取消另两档通过。原管理夹具1366×768、430×768四场景通过分类路径、全库切换、阅读和导入取消保留多选；4项Node入库使用检查、1项后端提示词版本/分类/保护检查通过。

证据 `<本地维护路径>`：selection-final为两库选择，multiple为资产多选补验，management为原管理页；selection保留初次夹具误点已关闭弹窗旧节点的失败材料，修正等待新节点后通过。实际查看四张选择截图及管理宽屏资产/窄屏提示词截图：纸色、原插画、阅读层次保留，长名换行，全文正常纵向滚动。使用真实顶部外壳但无生产连接/项目背景；取消检查在选择器返回边界，未重跑所有模式应用链。未生产重载、真实生成、提交或发布，最终体验仍待用户反馈。
