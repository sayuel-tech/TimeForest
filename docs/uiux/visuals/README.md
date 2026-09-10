# 美术、字体与样式层

先查 [具体保留清单与样式顺序](preservation.md)，再查 [18件现有图像及引用](assets.json)。不要因为动态引用未被字面检索找到就删除资源。

维护 ID：`visual`。关键词：美术、水彩、字体、颜色、CSS、插画、空态、尺寸。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

资源实际引用从 home/mode-registry/empty-state/image workspace 与 CSS 追踪；完整资源目录在 assets.json。

## 保留优先

用户要求保留现站优秀美术与有效 UI/UX。已查看首页水彩、电影空态历史样例；全体资源列为保留优先，不将每张图标记为用户单独认可。

## 修改边界及联动

style.css 是导入顺序，tokens 是基础色彩，design-tokens 是阅读与控件尺寸，task-layouts 在末尾调整任务布局；creation.css 是资产卡片的重要局部覆盖。字体既有中英文两处入口，勿只改一处。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/assets/fonts/fonts.css](../../../static/assets/fonts/fonts.css) | 文件入口 / 样式定义 |
| [static/studio/design-system.html](../../../static/studio/design-system.html) | 文件入口 / 样式定义 |
| [static/studio/style.css](../../../static/studio/style.css) | 文件入口 / 样式定义 |
| [static/studio/styles/base.css](../../../static/studio/styles/base.css) | 文件入口 / 样式定义 |
| [static/studio/styles/collection-navigation.css](../../../static/studio/styles/collection-navigation.css) | 文件入口 / 样式定义 |
| [static/studio/styles/components.css](../../../static/studio/styles/components.css) | 文件入口 / 样式定义 |
| [static/studio/styles/creation.css](../../../static/studio/styles/creation.css) | 文件入口 / 样式定义 |
| [static/studio/styles/design-tokens.css](../../../static/studio/styles/design-tokens.css) | 文件入口 / 样式定义 |
| [static/studio/styles/fonts/fonts.css](../../../static/studio/styles/fonts/fonts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/image-assets.css](../../../static/studio/styles/image-assets.css) | 文件入口 / 样式定义 |
| [static/studio/styles/library.css](../../../static/studio/styles/library.css) | 文件入口 / 样式定义 |
| [static/studio/styles/media-player.css](../../../static/studio/styles/media-player.css) | 文件入口 / 样式定义 |
| [static/studio/styles/modes.css](../../../static/studio/styles/modes.css) | 文件入口 / 样式定义 |
| [static/studio/styles/production-settings.css](../../../static/studio/styles/production-settings.css) | 文件入口 / 样式定义 |
| [static/studio/styles/prompt-library.css](../../../static/studio/styles/prompt-library.css) | 文件入口 / 样式定义 |
| [static/studio/styles/shell.css](../../../static/studio/styles/shell.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-center.css](../../../static/studio/styles/task-center.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/video-assembly.css](../../../static/studio/styles/video-assembly.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |
| [static/styles/tokens.css](../../../static/styles/tokens.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/visual.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

先定位实际计算样式的来源再改 token；入口与工作区分场景；宽窄/长文/媒体实际内容；美术原图与引用保留，不调用模型换图。

- [tools/check_ui_design.mjs](../../../tools/check_ui_design.mjs)
- [tests/ui_design.test.mjs](../../../tests/ui_design.test.mjs)
- [tests/creation_art_ui_fixture.py](../../../tests/creation_art_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/image-assets-art.md](../../image-assets-art.md)
- [docs/frontend/visual-design-standard-v2.md](../../frontend/visual-design-standard-v2.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。
