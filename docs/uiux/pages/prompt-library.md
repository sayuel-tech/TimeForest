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
