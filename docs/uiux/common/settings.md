# 参数与模型选择

维护 ID：`settings`。关键词：参数、模型、应用、恢复默认、制作参数。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

项目右上入口；公共外壳与各模式字段/保存适配分开。

## 保留优先

保留单入口、完整模型目录、临时副本取消与真实保存作用域。参数历史截图已查看。

## 修改边界及联动

公共外壳不拥有项目数据。图片参数权威在 h3ui/image_studio/parameters.py；前三视频在 capabilities/recipes；剧本/电影适配位于各自 workspace 内，不能假定只改原五模式即可。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/features/image-settings/index.js](../../../static/studio/features/image-settings/index.js) | `imageParameters`, `parseImageSeed`, `readImageParameter`, `createImageSettingsDraft`, `renderImageQuickSettings`, `openImageSettings` |
| [static/studio/features/workflow-settings/index.js](../../../static/studio/features/workflow-settings/index.js) | `createFeature` |
| [static/studio/modes/video-assembly/settings.js](../../../static/studio/modes/video-assembly/settings.js) | `visibleParameters`, `resetParameters`, `switchRecipe`, `settingsDialog` |
| [static/studio/styles/components.css](../../../static/studio/styles/components.css) | 文件入口 / 样式定义 |
| [static/studio/styles/production-settings.css](../../../static/studio/styles/production-settings.css) | 文件入口 / 样式定义 |
| [static/studio/ui/model-selector.js](../../../static/studio/ui/model-selector.js) | `modelSelector`, `bindModelSelectors` |
| [static/studio/ui/production-settings.js](../../../static/studio/ui/production-settings.js) | `openProductionSettings`, `parameterLoras`, `validateSettingsInputs`, `parameterGrid`, `parameterSlots`, `productionSettingsActions`, `productionGroups` |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/settings.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

打开/取消无写入；应用与保存可预测；完整值可核对；恢复默认只影响指定副本；目录变化保留选择。

- [tests/studio_parameter_dialog.test.mjs](../../../tests/studio_parameter_dialog.test.mjs)
- [tests/model_selection_ui_fixture.py](../../../tests/model_selection_ui_fixture.py)
- [tests/image_parameter_ui_fixture.py](../../../tests/image_parameter_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/parameter-map.md](../../frontend/parameter-map.md)
- [docs/frontend/parameter-and-interaction-contract.md](../../frontend/parameter-and-interaction-contract.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。
