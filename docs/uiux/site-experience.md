# R1 页面布局与原站美术接入

## 本次用户确认与边界

2026-09-10用户最新修订：首页恢复原版森林主视觉与创作入口布局，全站导航和连接状态恢复顶部，取消左侧全站栏。这两项明确覆盖此前R1位置要求；其他工作区的布局与信息密度继续按具体反馈维护。

2026-09-10 用户明确：网页的功能位置、区域划分、信息层级和操作布局以 R1 资料包预览为目标；只有纯粹的美术风格沿用原项目。这是本会话的新实施授权，与旧尺寸规范 V1 无关。保留品牌、本地字体、水彩原图和七模式独立插画，不使用离线原型示例项目或模拟运行逻辑替换原业务。

本记录描述已合回真实维护目录的实现及证据；当前进度与下一次接续只维护在[维护基线](../maintenance-baseline.md)。剧本／电影仍保留 v6.3.33“目前不可用、尚未完成整体体验验收”声明。布局接入、隔离 API 检查与用户实际体验分别记录；没有生产重载或 Git 发布。

## 实际接入与归属

| 区域 | 位置与行为 | 正式源码 |
|---|---|---|
| 全站 | 已按后续反馈恢复顶部品牌、任务／项目／资产／提示词／连接状态；回收站／存储归顶部更多，保留原离开保护与跳过导航 | static/index.html、app/bootstrap.js、ui/site-navigation.js、styles/shell.css |
| 首页 | 已按后续反馈恢复原版主视觉→全部创作方式→最近项目；不再以大幅最近作品占据首页 | pages/home.js、styles/shell.css |
| 公共工作区 | 页头→步骤→目录／主区／参考→底栏；目录与参考在窄屏按需展开，遮挡内容不可键盘误操作，关闭回到入口；步骤文字不隐藏 | ui/workspace-chrome.js、workspace-actions.js、workbench.js；styles/workbench.css 与 task-layouts.css |
| 剧本 | 原五页、跨页目录；上沟通下输出、只读记录对照；原候选和编辑节点移动后保留原绑定；已完成任务计时位于正文之后，进行中及失败状态仍优先展示 | modes/authoring/workspace.js、ui/experience-content.js |
| 资产落实 | 上方具名图像／声音／文字占位，类别与待落实筛选，名称／状态／来源／选素材；更多里保留上传、已有参考、关系、局部文字、合并与移除。补图入口在顶部工具行；下方完整资产剧本，无右属性栏 | features/authoring-assist/binding-cards.js、styles/creation.css |
| 电影生成 | 主播放器、结果动作、候选卡片；查看与采用／入库独立 | modes/movie/workspace.js、ui/experience-content.js、styles/workbench.css |
| 电影剪辑 | 主预览及右侧真实时长摘要→成片顺序→所选片段入出点／生成关系；连续预览与导出在底栏，缩放随轨道。预览明确是片段或本地顺序播放，不能冒充合成视频 | modes/movie/workspace.js、ui/experience-content.js、styles/creation.css |
| 原三视频 | 保留源片对照、原执行和参数；候选记录从右侧运行页签移至主对照区下方，原固定记录／查看／选用／入库／移除动作保留 | features/production/review.js、review-parts.js、styles/workbench.css |
| 图片／接续 | 公共外壳与当前素材／候选／轨道的原模块接入；图片画布遮罩与扩边仍用 ImageCanvas，接续 track_order 与导出仍用原服务 | 原模式控制器、styles/task-layouts.css |
| 两库与管理 | 左分类、主列表／正文、顶部查找与操作；保留固定版本、分页、取消、多选、三类回收、原备份与任务接口 | 原 pages 与 features；styles/collection-navigation.css、library.css、prompt-library.css |

表中的前端路径除 static/index.html 外均相对 static/studio。共同尺寸在 design-tokens.css，原颜色与字体在 static/styles/tokens.css。R1 的独立 experience.css 没有接入：布局规则按共同外壳、组件及模式责任归入原有文件，不维护第二套末尾换肤层。

## 草稿与数据契约

资产筛选按项目／分镜／片段范围保存在 ctx.bindingViews，只改变视图，不请求保存；绑定、固定资产版本、局部覆盖与引用登记复用原入口。未绑定、文字设定、不使用各有真实状态，不显示残留媒体冒充有效绑定。

timecode-input.js 显示分:秒.毫秒，执行仍提交整数毫秒。电影 ctx.timecodeDrafts 按生成片段／剪辑项和字段隔离原始输入及校验范围；非法输入不写入数值字段，保存失败后重绘仍保留文字；保存进行中时间码只读。原 save 门同时验证，保存成功或明确放弃才清理；播放取点定位主 media-player，避免候选缩略视频夺取读数。

ui/workbench.js 统一抽屉初始化、尺寸切换、背景 inert、Esc 与焦点返回；属性切换不重建输入。workspaceViewState 继续维护滚动、展开、焦点与同媒体节点。原 Session、revision、content_hash、确认、来源固定、运行提交与冲突门不变。

## 检查与证据

全部检查使用临时项目／临时库与假模型文件。原 Flask 路由和 ES Modules 直接运行，外部模型调用被 fixture 拒绝或由固定响应替身接管；没有安装环境或读取生产配置。包内原型的 65／24 项通过记录不并入本次结果。

- tests/site_layout_ui_fixture.py --r1：七模式共23个步骤，1440×960、760×900、430×900共69个页面；针对发现的抽屉和文字问题定向复核。一次浏览器启动未返回完成标记已在保留原失败记录后定向复核通过；检查宿主增加端口文件就绪保护，不记作业务通过。只证明所列页面和检查条件，不代表所有候选状态均已覆盖。
- tests/creation_experience_ui_fixture.py --r1：真实临时保存／确认／资产需求与已有参考绑定／筛选无写入和重绘保持／五页目录／对象作用域及固定写作响应。
- tests/creation_ui_fixture.py --r1：真实临时电影参数取消、固定生成末端及本地FFmpeg测试片、主播放器750ms取点、采用、时间轴保存、非法时间码失败留存、连续预览入口、返回父分镜与电影位置。
- tests/uiux_image_canvas_fixture.py：实际首页路由与图片蓝图，真实鼠标遮罩、撤销／重做、保存后的遮罩身份、96px扩边保存与任务隔离；0次引擎调用。提示词补记列表为显式空替身，不据此声称提示词收录通过。
- tests/library_layout_ui_fixture.py --r1：三档窗口下首页、项目档案、资产、提示词、导入、回收站、存储与任务入口，保留取消前多选。
- 48项相关 Node、7项临时 Python 检查通过。新时间码纯函数包含在 Node 数量内；不累计重复运行。体验结构与视觉结构只作静态辅助。

本机完整截图、DOM、JSON 与逐文件备份在 <本地维护路径>；before 是本轮开始的源码快照，source 是非生产接入副本，checks 是检查证据。这里只存本地验收材料，不把这些截图视为新增公开作品授权。

真实模型输出质量、长时多窗口与用户最终视觉／操作体验不在本次非生成检查结论中。没有通过的现场问题继续按具体反馈修复，不以截图或 CSS 引用代替整体功能可用声明。

## 回退

按本次 changed-files.json 对照 before 与 after 哈希，只恢复本批修改的文件；后续又有编辑的文件须人工合并，不整目录覆盖。新增文件先检查引用及后续改动。工作树外备份不含生产配置、数据库、模型或用户作品。原包安装器的回退只适用于其原始安装结果，不能对本次后续适配硬套。


最终整页复核补充：电影预览由模式的预览行限制高度，保证1440×960首屏可以同时到达轨道和入出点；资产输出的版本选择并入标题行，首屏可见正文开头。tests/creation_ui_fixture.py 与 creation_experience_ui_fixture.py 对这些实际位置增加断言，viewport-edit／viewport-asset 保存最终截图与通过记录。计时组件尺寸未改，已成功的写作任务计时位于正文之后。


首页／顶部导航修订：home.js复用R1接入前renderHome，继续使用当前projectCard的真实类型摘要。首页退出工作区专用tf-experience样式，恢复原有首页样式；其他模式保留该呈现。site-navigation读取顶栏实际高度并通知工作区重新计算空间；ResizeObserver随实例清理。窄屏导航可换行，没有左侧空白或重复顶栏。本次只检查受影响入口与工作区几何，不重复模型或业务全流程。6个普通页／任务入口和9个模式场景通过，证据在工作目录timeforest-home-topnav-20260910-111411/checks。


后续密度／字体／动效修复已在uiux-3完成，本文件初次R1尺寸描述属于接入历史；当前尺度和实际字体核对见[修复记录](../frontend/density-font-motion.md)。
