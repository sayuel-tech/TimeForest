# 资产库及选择器

维护 ID：`library`。关键词：资产库、素材、上传、导入、来源、派生、批量、收藏。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/assets` 列表；`#/assets/<id>` 详情；view=organize/tasks/storage/trash 为管理子视图。选择器为 pickLibraryAsset 弹窗，不能等同库管理页。

## 保留优先

保留分类与搜索、固定版本、整行预览及按需资料、来源追溯、可恢复移除。历史选择器截图已查看。

## 修改边界及联动

index.js 仍含列表、分类、处理任务与存储的组织；detail/media-tools 等分担详情。新增定位先看实际函数，不能想当然寻找独立 storage.js。使用登记在项目保存后，弹窗选择不等于已经使用。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/features/asset-picker/assembly-use.js](../../../static/studio/features/asset-picker/assembly-use.js) | `useImageInAssembly` |
| [static/studio/features/asset-picker/descendants-view.js](../../../static/studio/features/asset-picker/descendants-view.js) | `mountAssetDescendants` |
| [static/studio/features/asset-picker/destinations.js](../../../static/studio/features/asset-picker/destinations.js) | `acceptsImage`, `imageDestinations` |
| [static/studio/features/asset-picker/index.js](../../../static/studio/features/asset-picker/index.js) | `pickLibraryAsset` |
| [static/studio/features/asset-picker/library-client.js](../../../static/studio/features/asset-picker/library-client.js) | `libraryApi`, `uploadToLibrary`, `followTask` |
| [static/studio/features/asset-picker/media-view.js](../../../static/studio/features/asset-picker/media-view.js) | `primaryMedia`, `kindLabel`, `mediaSummary`, `thumbnail`, `mediaPlayer` |
| [static/studio/features/asset-picker/origin-view.js](../../../static/studio/features/asset-picker/origin-view.js) | `mountAssetOrigin` |
| [static/studio/features/asset-picker/project-use.js](../../../static/studio/features/asset-picker/project-use.js) | `useLibrary`, `selectionDialog` |
| [static/studio/features/asset-picker/result-import.js](../../../static/studio/features/asset-picker/result-import.js) | `resultAsset`, `loadResultReceipts`, `saveProjectMedia` |
| [static/studio/features/assets/index.js](../../../static/studio/features/assets/index.js) | `createFeature` |
| [static/studio/pages/asset-library/batch-actions.js](../../../static/studio/pages/asset-library/batch-actions.js) | `bindBatchActions` |
| [static/studio/pages/asset-library/detail.js](../../../static/studio/pages/asset-library/detail.js) | `mountDetail` |
| [static/studio/pages/asset-library/engine-settings.js](../../../static/studio/pages/asset-library/engine-settings.js) | `openLauncher` |
| [static/studio/pages/asset-library/import-dialog.js](../../../static/studio/pages/asset-library/import-dialog.js) | `openLibraryImports` |
| [static/studio/pages/asset-library/index.js](../../../static/studio/pages/asset-library/index.js) | `mountLibrary` |
| [static/studio/pages/asset-library/input-dialog.js](../../../static/studio/pages/asset-library/input-dialog.js) | `simpleInput` |
| [static/studio/pages/asset-library/media-timeline.js](../../../static/studio/pages/asset-library/media-timeline.js) | `bindTimeline` |
| [static/studio/pages/asset-library/media-tools.js](../../../static/studio/pages/asset-library/media-tools.js) | `mountMediaTools` |
| [static/studio/pages/asset-library/recycle-bin.js](../../../static/studio/pages/asset-library/recycle-bin.js) | `recycleCategories`, `recycleUrl`, `restoreRequest`, `recycleView`, `mountRecycleBin` |
| [static/studio/pages/asset-library/transfer.js](../../../static/studio/pages/asset-library/transfer.js) | `exportPack`, `importPack`, `collectFolder` |
| [static/studio/pages/asset-library/uploads.js](../../../static/studio/pages/asset-library/uploads.js) | `showUploads` |
| [static/studio/styles/collection-navigation.css](../../../static/studio/styles/collection-navigation.css) | 文件入口 / 样式定义 |
| [static/studio/styles/library.css](../../../static/studio/styles/library.css) | 文件入口 / 样式定义 |
| [static/studio/ui/asset-origin.js](../../../static/studio/ui/asset-origin.js) | `projectOriginLink`, `assetVersionLink`, `lineageMarkup`, `assetOriginMarkup` |
| [static/studio/ui/reference-assets.js](../../../static/studio/ui/reference-assets.js) | `importOptions`, `referenceAssetCard` |
| [static/studio/ui/reference-metadata.js](../../../static/studio/ui/reference-metadata.js) | `referencePurposes`, `needsSubject`, `referenceMetadata`, `chooseReferenceMetadata` |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/library.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

取消保留调用页草稿；返回保留筛选/滚动；绑定到明示对象；来源不拿当前项目参数冒充历史；移除与恢复按原归属。

- [tests/library_layout_ui_fixture.py](../../../tests/library_layout_ui_fixture.py)
- [tests/library_transfer_ui_fixture.py](../../../tests/library_transfer_ui_fixture.py)
- [tests/asset_origin_ui_fixture.py](../../../tests/asset_origin_ui_fixture.py)
- [tests/studio_library_usage.test.mjs](../../../tests/studio_library_usage.test.mjs)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/asset-library-architecture.md](../../asset-library-architecture.md)
- [docs/asset-library-maintenance.md](../../asset-library-maintenance.md)
- [docs/recycle-bin.md](../../recycle-bin.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

顶部查找／导入、左侧分类与主列表沿用原接口，取消保留多选；原站水彩图与本地字体保留。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 查找、整理和复用素材。
- **第一眼最想看见什么？** 可辨认素材及有效分类、搜索结果；不是巨幅图库宣传页。
- **最自然的动作：** 查找 → 预览 → 必要时整理 → 加入创作
- **空间判断：** 列表兼顾缩略图与关键信息；详情给完整预览和来源适当空间；选择器聚焦选素材，不强塞管理页全部功能。
- **必须保留：** 原固定引用、入库去重、来源跳转、派生追溯、回收和多选。
- **直接验收场景：** 在库管理与模式内选择分别检查；取消保留原选择，不改变项目；资产来源不伪造。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。


## Q6a查找与固定选择（2026-09-12）

资产管理页保留原分类、搜索、多选工具栏和素材网格；选择器保留整行预览与来源。修正选择卡长名称单行截断，允许完整换行；补当前分类/搜索/结果数、选择或勾选动作，预览明确引用此固定版本。筛选空结果提示调整条件，不再一律要求上传。未改变版本读取、项目绑定或管理动作。

新增 [两库选择上下文夹具](../../../tests/library_selection_context_ui_fixture.py)，真实临时库/API与现有站内插画，禁止生成引擎访问。两库选择1366×768、430×900四场景通过：空搜索恢复、长名称和全文、返回保留筛选、取消返回null、资产固定版本、提示词历史版本1与当前版本2区分；资产多选勾选与取消另两档通过。原管理夹具1366×768、430×768四场景通过分类路径、全库切换、阅读和导入取消保留多选；4项Node入库使用检查、1项后端提示词版本/分类/保护检查通过。

证据 `<本地维护路径>`：selection-final为两库选择，multiple为资产多选补验，management为原管理页；selection保留初次夹具误点已关闭弹窗旧节点的失败材料，修正等待新节点后通过。实际查看四张选择截图及管理宽屏资产/窄屏提示词截图：纸色、原插画、阅读层次保留，长名换行，全文正常纵向滚动。使用真实顶部外壳但无生产连接/项目背景；取消检查在选择器返回边界，未重跑所有模式应用链。未生产重载、真实生成、提交或发布，最终体验仍待用户反馈。
