# UI/UX 按任务维护索引

用途：先定位，再按需读取；不要一开始加载全部文档或机器图。当前交付与未完成项只在 [维护基线](../maintenance-baseline.md) 维护。先读 [盘点结论](audit/inventory.md)，有具体改动时通常只需一份页面卡和一份公共专题。

**保留现有优秀美术和符合需求的 UI/UX；全站评估不等于全部替换。** 用户认可、源码事实、历史截图与待验证判断分别记录。

## 从用户任务进入

| 要改什么 | 第一入口 | 可能联动 |
|---|---|---|
| 首页、新建、项目档案 | [首页/项目](pages/home-projects.md) | [导航](common/shell-navigation.md) |
| 换人 | [换人](pages/swap.md) | [视频正文/审核](common/production.md) |
| 参考图长视频 | [参考图](pages/image-story.md) | 视频正文/审核 |
| 文生视频 | [文生](pages/text-story.md) | 视频正文/审核 |
| 图片任务、画布、候选 | [图片](pages/image-assets.md) | [参数](common/settings.md) |
| 视频接续、轨道、拼接 | [接续](pages/video-assembly.md) | [状态](common/state-feedback.md) |
| 剧本、资产绑定、分镜、Prompt | [剧本](pages/authoring.md) | [跨页流程](workflows/README.md) |
| 电影片段与剪辑 | [电影](pages/movie.md) | 跨页流程 |
| 资产库、选择器、来源 | [资产](pages/asset-library.md) | [管理](pages/management.md) |
| Prompt 查找/全文/应用 | [提示词](pages/prompt-library.md) | 状态 |
| 任务、回收站、存储 | [管理](pages/management.md) | 资产、状态 |
| 页头、底栏、列数、属性栏 | [导航与空间](common/shell-navigation.md) | 美术与样式 |
| 保存、取消、弹窗、刷新、计时 | [状态与反馈](common/state-feedback.md) | 参数、受影响模式 |
| 插画、字体、颜色、CSS | [美术与样式](visuals/README.md) | [具体资产表](visuals/assets.json) |

## 调阅与更新

- [已确认问题/待复核项](audit/findings.md)：每项有依据，不把旧问题全部重开。
- [本轮视觉证据范围](audit/evidence.md)：8张历史截图的观察与局限。
- [维护约定](maintenance.md)：新增页面/组件/资源后如何更新。
- [机器目录](catalog.json)：稳定 ID、关键词、文档与源文件模式。可用脚本 `--topic authoring` 只输出所需条目。
- [具体保留清单](visuals/preservation.md)：已有插画、字体、计时和有效交互的定位与保留依据。
- [验证入口](verification.md)：链接、源图漂移和定向业务检查分开。

详细字段仍查 [参数映射](../frontend/parameter-map.md)，公共契约仍查 [共享 UI](../frontend/shared-ui.md)，设计原则仍查 [设计规范 V2](../frontend/visual-design-standard-v2.md)。此目录负责定位、保留边界与证据，不复制第二套产品规范。

## 已认可原型的全站接入

[全站体验接入与验证边界](site-experience.md)：2026-09-10 用户确认功能位置与布局采用R1资料包，美术保留原项目。该记录对应已合回本地的实现与隔离检查；不表示生产加载、真实生成或整体体验已验收，不替代维护基线。


最新首页／全站栏修订：用户要求恢复原版首页与顶部导航，覆盖R1这两处位置；按[首页卡](pages/home-projects.md)和[公共壳层](common/shell-navigation.md)维护。其他模块的信息密度反馈仍见维护基线。
