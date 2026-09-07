# 公共界面组件与模式适配

本地6.3.13按[优化方案](../product/shared-ui-optimization-plan.md)接入。共同样式修改从以下入口进行，各模式保留自己的草稿、参数定义和执行逻辑。

| 共同呈现 | 唯一入口（相对static/studio） | 调用方与边界 |
|---|---|---|
| 制作参数完整弹窗 | ui/production-settings.js：openProductionSettings、productionSettingsMarkup、productionSettingsActions；styles/production-settings.css | workflow-settings服务三个视频模式，image-settings服务图片，video-assembly/settings服务拼接；根容器由公共入口创建，样式匹配.production-settings，不再依赖调用方填写ID |
| 模型文件选择 | ui/model-selector.js：modelSelector / bindModelSelectors，由production-settings调用 | 五模式底模、编码器、VAE与LoRA；完整目录下拉＋折叠手动输入，委托绑定跟随公共弹窗实例，保存仍交业务适配 |
| 步骤底栏 | ui/workspace-actions.js：workspaceActions / workspaceActionGroups；styles/workbench.css | 视频editor-parts、图片imageActionBar、拼接workspace；左支持区、右次动作与主动作，业务决定动作含义 |
| 导入选项与参考素材卡 | ui/reference-assets.js：importOptions / referenceAssetCard；styles/workbench.css中的属性区样式 | 视频authoring/assets与拼接references；图片画布输入保留专属原图角色选择，使用原公共控件，不借此改变画布交互 |
| 工作台和侧栏 | ui/workbench.js | rail/canvas/inspector插槽，propertyTabs及键盘选择；页签由当前步骤配置，超宽可滚动 |
| 时间与错误 | ui/run-timing.js、ui/error-feedback.js | 保持原有真实时间、终态和错误来源适配 |

完整参数入口返回当前实例的dialog/content/closed/close/alive。底层复用scopedModal与焦点控制，前次请求只能操作自己的实例；关闭后closed结束等待。图片仍由原草稿事务处理取消、默认、应用和请求中断，保存门与遮罩流程不变。三个视频仍应用到项目草稿；拼接可应用或显式保存。共同按钮按恢复默认、取消、应用、保存排列，缺少的业务动作不造假按钮。

组件提供共同框架、控件、动作和样式。字段组内容/LoRA槽按能力组合，模式允许插入说明和特殊字段，但不另写弹窗宽度、标题、导航或按钮区CSS。保留#settings-content仅作已有检查/查询兼容标记，视觉不得依赖该ID。

扩展时先列公共内容和专属行为，再选这些入口。改变公共美观度时只改共同层，并核对五模式全部调用；修改字段语义时另核对API→保存→运行快照→编译节点。不能只用公共函数引用或“无溢出”当作验收。

状态读取也必须遵守草稿归属：watchProject只负责请求时序，业务receive负责是否接收。无变化响应不得替换仍由DOM事件闭包引用的对象；替换对象必须与重绘/重新绑定同步。请求发出后可能才开始编辑或打开弹窗，因此接收时也检查dirty、working、弹窗及输入焦点。因播放而暂缓重绘时应同时暂缓替换，不能只推迟render。视频接续6.3.15修复这一对象脱节；原视频ProjectSession已有签名/版本判断，本轮不改共同轮询周期或其他模式。

步骤隐藏或移除某业务面板时，不得因仍有选中的业务对象就绑定不存在的控件；video-assembly/references在实际素材面板存在时才绑定。草稿回归必须包含等待正常轮询后输入、迟到响应及保存失败，而不只检查打开页面后立即填写。

检查入口：tests/shared_ui_fixture.py以三个视频模拟API、图片真实隔离API验证四模式；tests/video_assembly_ui_fixture.py用真实隔离API验证拼接。1280×720、1920宽屏、760窄屏核对实际参数容器、字号、字段网格、按钮区可达及取消重开；素材和动作位置另做串联检查。实际通过数量、截图和后端加载状态只记在[维护基线](../maintenance-baseline.md)。

视频接续6.3.16：轨道是业务适配，继续使用公共workbench与底栏，不复制公共布局。track.js投影原片/已选续接，workspace显示轨道并保存排序；导出清单与后台track_order一致。不要用增加源视频副本的方式显示生成结果，避免重复导出、来源丢失或候选失去归属。

6.3.18：五模式的底模、编码器、VAE、加速/普通LoRA统一使用 `ui/model-selector.js`：下拉展开完整目录，不以当前文件名过滤；“手动填写文件名”折叠区保留完整相对路径。目录外的当前值继续保留并提示，输入、选择、刷新均不自动替换模型。公共productionSettingsMarkup为目录区提供production-settings-directory容器；说明/刷新操作与分类区统一留白和分隔，不由模式补margin。续接参数只在条件字段需要时重绘，选择/手动编辑模型不销毁当前控件。

模型回归入口tests/model_selection_ui_fixture.py：真实临时API扫描假文件，检查两条续接配方的目录选择、手动输入、刷新、取消、保存与离线底模节点绑定；tests/shared_ui_fixture.py同时核对其他四模式控件及间距。检查无需ComfyUI，不证明文件组合的生成效果。

视频接续6.3.19：modes/video-assembly/import-dialog.js只配置“添加视频”业务选项，复用scopedModal的外壳/焦点/关闭和importOptions的来源布局，不新增私有弹窗CSS。第二/三步目录加号原地打开，第一步保留右侧导入页。workspace中的importFiles/importLibrary同时服务侧栏与弹窗，经原save与导入接口追加轨道；取消保持草稿，保存失败不继续导入，关闭路由时来源选择随signal取消。检查入口tests/assembly_import_ui_fixture.py使用真实临时API、临时视频和库，覆盖两种导入、步骤保持、取消及模拟保存冲突阻断。
