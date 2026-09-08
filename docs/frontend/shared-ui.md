# 公共界面组件与模式适配

本地6.3.13按[优化方案](../product/shared-ui-optimization-plan.md)接入。共同样式修改从以下入口进行，各模式保留自己的草稿、参数定义和执行逻辑。

| 共同呈现 | 唯一入口（相对static/studio） | 调用方与边界 |
|---|---|---|
| 制作参数完整弹窗 | ui/production-settings.js：openProductionSettings、productionSettingsMarkup、productionSettingsActions；styles/production-settings.css | workflow-settings服务三个视频模式，image-settings服务图片，video-assembly/settings服务拼接；根容器由公共入口创建，样式匹配.production-settings，不再依赖调用方填写ID |
| 模型文件选择 | ui/model-selector.js：modelSelector / bindModelSelectors，由production-settings调用 | 五模式底模、编码器、VAE与LoRA；完整目录下拉＋折叠手动输入，委托绑定跟随公共弹窗实例，保存仍交业务适配 |
| 项目页头与步骤 | ui/workspace-chrome.js：workspaceHeader / workspaceSteps / bindWorkspaceSteps；styles/workbench.css | 五模式控制器与图片视图；同一结构/焦点导航，模式提供标题、状态、步骤、原选择器与保存门 |
| 步骤底栏 | ui/workspace-actions.js：workspaceActions / workspaceActionGroups；styles/workbench.css | 视频editor-parts、图片imageActionBar、拼接workspace；左支持区、右次动作与主动作，业务决定动作含义 |
| 导入选项与参考素材卡 | ui/reference-assets.js：importOptions / referenceAssetCard；styles/workbench.css中的属性区样式 | 视频authoring/assets与拼接references；图片画布输入保留专属原图角色选择，使用原公共控件，不借此改变画布交互 |
| 工作台和侧栏 | ui/workbench.js | rail/canvas/inspector插槽，propertyTabs及键盘选择；页签由当前步骤配置，超宽可滚动 |
| 时间与错误 | ui/run-timing.js、ui/error-feedback.js | 保持原有真实时间、终态和错误来源适配 |

完整参数入口返回当前实例的dialog/content/closed/close/alive及run/showError/cancel。底层复用scopedModal与焦点控制，前次请求只能操作自己的实例；关闭后closed结束等待。图片仍由原草稿事务处理取消、默认、应用和请求中断，保存门与遮罩流程不变。本地6.3.22五模式均可应用或显式保存；原三视频/图片/接续通过各自原保存门持久化。共同按钮按恢复默认、取消、应用、保存排列，缺少的业务动作不造假按钮。

组件提供共同框架、控件、动作和样式。字段组内容/LoRA槽按能力组合，模式允许插入说明和特殊字段，但不另写弹窗宽度、标题、导航或按钮区CSS。保留#settings-content仅作已有检查/查询兼容标记，视觉不得依赖该ID。

扩展时先列公共内容和专属行为，再选这些入口。改变公共美观度时只改共同层，并核对五模式全部调用；修改字段语义时另核对API→保存→运行快照→编译节点。不能只用公共函数引用或“无溢出”当作验收。

状态读取也必须遵守草稿归属：watchProject只负责请求时序，业务receive负责是否接收。无变化响应不得替换仍由DOM事件闭包引用的对象；替换对象必须与重绘/重新绑定同步。请求发出后可能才开始编辑或打开弹窗，因此接收时也检查dirty、working、弹窗及输入焦点。因播放而暂缓重绘时应同时暂缓替换，不能只推迟render。视频接续6.3.15修复这一对象脱节；原视频ProjectSession已有签名/版本判断，本轮不改共同轮询周期或其他模式。

步骤隐藏或移除某业务面板时，不得因仍有选中的业务对象就绑定不存在的控件；video-assembly/references在实际素材面板存在时才绑定。草稿回归必须包含等待正常轮询后输入、迟到响应及保存失败，而不只检查打开页面后立即填写。

检查入口：tests/shared_ui_fixture.py以三个视频模拟API、图片真实隔离API验证四模式；tests/video_assembly_ui_fixture.py用真实隔离API验证拼接。1280×720、1920宽屏、760窄屏核对实际参数容器、字号、字段网格、按钮区可达及取消重开；素材和动作位置另做串联检查。实际通过数量、截图和后端加载状态只记在[维护基线](../maintenance-baseline.md)。

视频接续6.3.16：轨道是业务适配，继续使用公共workbench与底栏，不复制公共布局。track.js投影原片/已选续接，workspace显示轨道并保存排序；导出清单与后台track_order一致。不要用增加源视频副本的方式显示生成结果，避免重复导出、来源丢失或候选失去归属。

6.3.18：五模式的底模、编码器、VAE、加速/普通LoRA统一使用 `ui/model-selector.js`：下拉展开完整目录，不以当前文件名过滤；“手动填写文件名”折叠区保留完整相对路径。目录外的当前值继续保留并提示，输入、选择、刷新均不自动替换模型。公共productionSettingsMarkup为目录区提供production-settings-directory容器；说明/刷新操作与分类区统一留白和分隔，不由模式补margin。续接参数只在条件字段需要时重绘，选择/手动编辑模型不销毁当前控件。

模型回归入口tests/model_selection_ui_fixture.py：真实临时API扫描假文件，检查两条续接配方的目录选择、手动输入、刷新、取消、保存与离线底模节点绑定；tests/shared_ui_fixture.py同时核对其他四模式控件及间距。检查无需ComfyUI，不证明文件组合的生成效果。

视频接续6.3.19：modes/video-assembly/import-dialog.js只配置“添加视频”业务选项，复用scopedModal的外壳/焦点/关闭和importOptions的来源布局，不新增私有弹窗CSS。第二/三步目录加号原地打开，第一步保留右侧导入页。workspace中的importFiles/importLibrary同时服务侧栏与弹窗，经原save与导入接口追加轨道；取消保持草稿，保存失败不继续导入，关闭路由时来源选择随signal取消。检查入口tests/assembly_import_ui_fixture.py使用真实临时API、临时视频和库，覆盖两种导入、步骤保持、取消及模拟保存冲突阻断。

## 6.3.21复用覆盖复核（分析，未实施）

[本次复用分析](../ui-code-reuse-audit-20260908.md)根据真实调用方确认：参数完整外壳、模型选择、计时和工作台已经共用；仍有三套项目页头/步骤模板、换人第一步手写底栏、原三视频部分错误未接公共反馈、LoRA/目录内部组合和种子控件覆盖不足。接续候选/播放器与普通输入选择弹窗也存在重复。后续应补齐已有入口，并按模式传内容和行为，不把已有规范描述当作全部调用方已经统一。

保存/轮询适合共用防重、取消和实例/版本保护机制；各模式payload、影响确认、token补登记与生成状态机继续独立。上述建议本轮未改业务或样式，后续验收需覆盖实际调用方。

## 共同体验目标（2026-09-08，方案待实施）

用户要求五模式具有同一套可学习、可预测的操作习惯，不能只统一公共HTML/CSS。最新[体验一致性方案](../product/experience-consistency-plan.md)定义保存/应用/取消、返回、导入、生成、选用与入库的目标语义、共同位置和验收脚本。组件需同时拥有共同呈现和交互生命周期，模式提供真实业务内容与命令，不自行改变公共动作含义。

本地6.3.22已落地参数/保存与离开保护的首批闭环，后续继续导航与位置、生成挑选及异步可靠性；每批横向核对五模式。现有候选、轨道、画布、快照与工作流保护保留，具体数据结构不强并。此段是目标与维护原则，未证明全部调用方已符合方案。

## 新增功能保持统一

公共入口登记在[体验接入清单](experience-contract.json)，开发与验收执行[体验准入](experience-admission.md)。清单引用真实公共文件，不代替本文的职责说明。新增功能先选完整组件，再写业务适配；缺能力先补公共入口，不能复制公共呈现。公共修改同批检查所有受影响模式，登记、实际交互及视觉证据分别核对。现有五模式保留baseline缺口，未按完整共同脚本验收前不转为已完成。

## 6.3.22参数与保存交互

详见[首批交付](experience-phase1.md)。production-settings的run统一校验前置、防重、忙碌时编辑/关闭保护与错误原文；parameterLoras统一三视频和接续的槽位呈现，seedFields保留片段/任务作用域。ui/choice-dialog.js承接影响确认与离开三选项，ui/draft-status.js提供共同状态文案。参数保存失败保留临时副本和已合入的未保存草稿，取消不撤销已经合入的变化。新增调用方复用完整入口与各自保存门，不复制生命周期。

## 第二批公共导航与底栏（本地6.3.23）

五模式均经workspace-chrome，换人第一步也经workspaceActions；图片不再覆盖窄屏savebar样式。保存/返回在左，检查/下一步/主动作在右；图片结果为空时返回仍在左边。换人/图片导入选项复用importOptions，保留角色与原图目标。新模式需登记chrome；普通页面改动也按同一准入执行。实现、宽窄跨模式检查与尚未覆盖场景见[第二批交付](experience-phase2.md)。第三批候选/播放进度见下文，完整异步仍未收口，不把模板收敛视作全站验收。

## 第三批结果与播放（本地6.3.24）

`ui/result-view.js`统一candidateState/candidateButton、resultActions及collectionActions；查看与决定在左、下载与收藏在右，workbench.css负责响应式。图片与接续用共同候选按钮，三视频历史保留details并复用状态/动作；原成片也用共同栏。四视频统一mediaPlayer/bindMediaPlayers，接续仅传id/class及尾部连播来源，不能另写播放器尺寸或裁切掩盖媒体问题；事件绑定与dispose按工作区生命周期，业务播放定位公共播放器。

移除/恢复沿candidate-records的业务适配，不新增删除状态。前三视频入库回执由asset-picker/result-import按工作区实例保存，仅真实任务成功才标已入库，刷新不伪造持久状态。实际语义、检查及剩余第四批见[第三批交付](experience-phase3.md)。新调用方按results/playback准入声明复用或不适用；无状态的结果外壳不能替代各模式的保存、审核与选用门。

## 第四批异步机制（本地6.3.25）

`core/async-state.js`管理readStamp/currentRead/canReplaceDraft及未知提交检查；`progress-channel.js`只读轮询且不重发写请求，图片与四视频共同接入。模式保留各自状态数据，暂缓整树替换时可只更新运行事实；必须保留草稿对象与编辑代次。`ui/async-feedback.js`提供稳定连接/传输反馈，成功读取清连接错误；`core/task-state.js`统一队列/待确认等事实，生成业务可增加子阶段。

`upload-client.js`的uploadForm复用原XHR传输，uploadAsset保留原包装；api提供进度回调供三个控制器适配，不迁移资产库分块协议。`modalTicket`使初始异步目录查询在取消/路由切换后失效，选择器再以signal/序号保护具体搜索。原三视频入库回执不再限于会话缓存，outputs读取成功操作和实际资产；工作区仅缓存呈现，无回写。旧进程需加载result_receipts_version=1。完整调用方、检查及未验范围见[第四批交付](experience-phase4.md)。


## 公共资产来源与预览（6.3.26）

ui/asset-origin.js提供来源面板、项目状态链接和固定资产链接；ui/source-parameters.js提供只读参数折叠，图片imageProductionGroups与实际图片参数页共用。features/asset-picker/origin-view.js承接真实请求/错误/迟到响应，详情和选择器复用。公共referenceAssetCard、图片A/B、接续原片及换人源视频使用同一个assetVersionLink；不在模式内拼来源标签或猜项目。来源模块不引用具体工作区，旧接续展示入口只转导出。详细验收见[资产交付](../asset-experience-20260908.md)。

## 来源记录定位（6.3.27）

公共core/source-target.js将固定来源查询解析为只读查看状态，ui/source-navigation.js统一提示/返回资产/回收入口。三个workspace控制器只适配位置，不复制身份规则或改变已选用结果。origin_*与asset导入查询隔离；历史成片缺身份不定位最新导出。公共容器复用notice/row/quiet，不增加模式CSS。详见[定位交付](../asset-source-navigation-20260908.md)。

## 素材用途与取消（6.3.28）

ui/reference-metadata.js提供referencePurposes、referenceMetadata及chooseReferenceMetadata，只返回用户意图。前三视频本地上传/编辑、接续库/本地添加及编辑共用对话框；库转入与绑定列表共用用途定义。确认后模式才做上传、草稿变更或保存，取消/关闭/Abort均不调用提交。图片A/B保留角色槽业务，移除仅清引用；详情见[资产核心流程](../asset-lifecycle-20260908.md)。

## 提示词公共体验（6.3.32）

公共工具栏和展开编辑外壳为ui/prompt-editor.js，业务协调在features/prompt-library/tools.js；后者使用同目录browser/editor适配库页面与选择器。ui层不倒依赖feature；adapters按当前目标及允许字段应用patch。三个工作区控制器和原视频编辑器绑定同一个入口，不另写模式按钮/CSS。取消不写草稿，应用不保存，收藏不生成；保存成功由后端统一收录。错误复用error-feedback，补记失败与项目保存状态分开。

模板编辑与分类编辑离开时经共同确认，scopedModal的onScopedClose只在当前关闭时收尾，避免旧close事件关闭刚打开的选择器。结果与资产来源的生成文字共用features/prompt-library/records.js，固定版本与project跳转复用原来源组件。具体使用、边界、代码及五模式必要检查见[提示词库](../prompt-library.md)。新功能按准入声明promptEditing/promptCollection/promptRecords，不能复制私有模板。
