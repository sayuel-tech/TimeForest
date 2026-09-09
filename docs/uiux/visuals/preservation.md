# 具体美术与交互保留清单

用户明确要求保留已有优秀部分；以下“保留优先”不是每件成品均已获单独认可。机器资源表记录18件现有图像资产、哈希与文字引用；空引用可能来自动态路径，绝不代表可删除。

| 成品/机制 | 实际位置（仓库根相对路径） | 使用位置/保留依据 |
|---|---|---|
| 品牌标记与 favicon | static/assets/brand/brand-mark.svg、favicon.svg | static/index.html；既有品牌身份，保留优先 |
| 首页导演桌面图及窄屏图 | static/assets/hero/hero-director-desk.webp、hero-director-desk-mobile.webp | pages/home.js 的 picture；两幅对应不同窗口，不随意合并 |
| 换人、参考图、文生入口图 | static/assets/modes/mode-rv2v.webp、mode-r2v.webp、mode-t2v.webp | mode-registry 注册；现站风格基础，参考图历史页面已查看 |
| 图片入口图 | static/assets/modes/mode-image-assets.webp | 注册表；角色/服装/场景主题，原美术说明有制作依据 |
| 视频接续入口图 | static/assets/modes/mode-video-continuation.webp | 注册表；沿用胶片与森林主题 |
| 剧本、电影入口图 | static/assets/modes/mode-authoring.webp、mode-movie.webp | 注册表；五项 V3 美术中的两项，历史首页样例已查看 |
| 图片画布/候选空态 | static/assets/image-studio/empty-editor.webp、empty-results.webp | features/image-results/workspace-view.js；已有内容时不能让装饰图挤占画布 |
| 剧本空态 | static/assets/authoring/empty-story.webp | ui/empty-state.js 的动态路径与剧本调用；不能因字面匹配遗漏而误删 |
| 电影候选/剪辑空态 | static/assets/movie/empty-takes.webp、empty-edit.webp | modes/movie/workspace.js；历史候选空态已查看 |
| 旧有项目/镜头空态 | static/assets/empty/empty-projects.svg、empty-shot.svg | home、editor-parts、export、设计检查页；属于仍有引用资源 |
| 中英文文字体系 | static/assets/fonts/fonts.css；static/studio/styles/fonts/fonts.css | style.css 与 static/styles/tokens.css 两条导入链，保留本地字体与字形覆盖 |
| 纸色/墨色/森林绿与阅读尺度 | static/styles/tokens.css；static/studio/styles/design-tokens.css | 颜色角色与17px阅读/16px摘要等是当前源码值；具体调整须检查调用方 |
| 图片计时呈现及共同运行状态 | static/studio/ui/run-timing.js；styles/components.css | AGENTS 明确记载用户认可图片计时，并作为共同呈现依据 |
| 同一会话列表/全文切换 | features/prompt-library/browser.js；ui/prompt-editor.js | 原阅读改造与本次历史截图支持保留方向，未重验全部交互 |
| 草稿/返回/媒体保护 | core/async-state.js、snapshot-update.js；ui/workspace-view-state.js | 当前公共机制，不能因布局重构而丢弃 |

实际可点击路径及引用表见 [资源清单](assets.json)、[视觉源码卡](README.md) 和 [状态卡](../common/state-feedback.md)。按“入口—素材—CSS—使用场景”定位后再改，不以整站换皮替代问题分析。

## 样式维护顺序

1. style.css 只组织加载；不要将全部新 CSS 堆到这里。
2. static/styles/tokens.css 与 design-tokens.css 定义基础角色；全局更改影响多个页面。
3. shell/workbench 管外壳、目录和主区域；components 管共同控件与状态。
4. library/prompt-library/image-assets/video-assembly/creation 等处理特定任务。
5. collection-navigation 与最后导入的 task-layouts 仍可覆盖前面布局；必须核对最终匹配规则。资产页 creation.css 内部也有同选择器后置覆盖。

保留清单随实际修改维护。已获认可的特征应说明保留方式；需替换时说明当前任务为何不足及局部调整为何不能解决，不预设全部图片或布局必须重新制作。
