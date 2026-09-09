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
