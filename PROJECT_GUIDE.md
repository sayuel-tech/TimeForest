# 时间森林项目地图

唯一维护来源：`<仓库根目录>`。当前状态与交接只写在 [维护基线](docs/maintenance-baseline.md)，长期规则与读取顺序见 [AGENTS](AGENTS.md)。本文件只定位代码和现行说明，不另维护版本台账或参数表。

按用户功能定位；同用途新工作流加到原模块。家族级代码复用可以继续，模型世代变化不自动成为新增页面或模块的理由。

| 工作内容 | 真实实现入口（相对仓库根目录） | 现行说明 |
|---|---|---|
| 参数/保存与离开保护 | `static/studio/ui/{production-settings,choice-dialog,draft-status}.js`；三个控制器的saveBeforeLeave | [6.3.22首批交付](docs/frontend/experience-phase1.md)，tests/experience_settings_ui_fixture.py与tests/experience_assembly_ui_fixture.py；共用操作生命周期，保留原保存作用域 |
| 页头、步骤与底栏 | `static/studio/ui/{workspace-chrome,workspace-actions}.js`、`styles/workbench.css`；三类控制器适配 | [6.3.23第二批交付](docs/frontend/experience-phase2.md)，tests/workspace_navigation_ui_fixture.py；统一定位与键盘焦点，保留原业务保存/准备门 |
| 五模式公共界面 | `static/studio/ui/{production-settings,model-selector,workspace-actions,reference-assets,workbench}.js`、`static/studio/styles/production-settings.css`与各业务适配 | [公共组件归属](docs/frontend/shared-ui.md)；完整参数外壳、完整目录模型选择/手动文件名、动作分组、视频素材卡；隔离多模式检查tests/shared_ui_fixture.py，模型选择→保存→离线编译检查tests/model_selection_ui_fixture.py |
| 状态轮询与输入草稿保护 | `static/studio/core/{progress-channel,project-session}.js`；接续适配在`modes/video-assembly/workspace.js`的receive；`tests/video_assembly_draft_ui_fixture.py` | [草稿接收规范](docs/frontend/shared-ui.md)；无变化保持对象、迟到响应不能覆盖编辑、保存失败阻止提交；隔离API→保存→运行快照检查 |
| 视频接续与AI尾部续接 | `h3ui/video_assembly/{service,references,source_parameters,track,compiler,media,routes}.py`、`static/studio/modes/video-assembly/{workspace,import-dialog,source-parameters,track,settings}.js`、`static/studio/styles/video-assembly.css`；`tests/test_video_assembly.py`、`tests/studio_video_assembly.test.mjs`、`tests/video_assembly_ui_fixture.py`、`tests/test_video_assembly_track.py`、`tests/video_assembly_track_ui_fixture.py`、`tests/assembly_import_ui_fixture.py`、`tests/test_video_assembly_tail_geometry.py` | [现行说明](docs/video-assembly.md)、[原计划](docs/product/video-assembly-plan.md)；独立序列与两条续接适配，纯拼接不依赖ComfyUI，真实生成待验 |
| GitHub代码与独立工作流包 | 当前源码筛选导出；六个原始工作流、五个图片与两个续接API示例、模型及节点TXT独立压缩 | [独立分发](docs/release-distribution.md)含GitHub Release附件下载与校验入口；保留原维护历史，公开快照排除工作流/模型清单包/个人资料，补包后离线验证 |
| GitHub项目介绍与功能表述 | `docs/project-introduction.zh-CN.md`、`docs/images/`、`docs/product/tool-comparison.md`；公开README同步图文，原维护README保留安装入口 | [GitHub分享](docs/github-sharing.md)；正式介绍以视觉设计和交互体验开篇，再说明四模式、迭代制作与资产复用；生成效果和硬件能力按真实证据表述 |
| 启动、组装与页面 | `start.bat`、`run.py`、`h3ui/__init__.py`、`static/index.html`、`static/studio/app.js` | [README](README.md)、[维护基线](docs/maintenance-baseline.md)；`--no-startup-recovery` 仅抑制本次启动恢复，默认行为不变 |
| 桌面菜单与网站启动停止 | `tools/director-menu.cmd`、`tools/director_service.ps1`、`tests/director_service.tests.ps1`；桌面 `启动时间森林导演台.cmd` 为绝对路径转接 | [启动停止菜单](docs/director-launcher.md)；复用当前配置与现有环境、准确进程核对、隐藏运行及本地日志 |
| 功能导航、三个视频工作区 | `static/studio/app/mode-registry.js`、`static/studio/modes/{swap,image-story,text-story}/workspace.js` | [模块约定](docs/product/module-contracts.md)、[前端结构](docs/frontend/README.md) |
| 图片工作区与任务 | `static/studio/app/image-workspace-controller.js`、`core/image-session.js`、`features/image-results/workspace-view.js`、`features/image-canvas/index.js`（后三者均在 `static/studio/`） | [图片模块](docs/image-assets.md)、[图片 UI](docs/frontend/image-workspace-ui.md)；任务废弃/恢复在 `h3ui/image_studio/service.py`/`routes.py`，零任务空态保留新增入口 |
| 五模式公共计时与运行时间 | `static/studio/ui/run-timing.js`、`ui/primitives.js`；图片 workspace-view、视频 production/records、source-preparation、export（均在 `static/studio/`）；`tests/studio_run_timing.test.mjs`、`tests/studio_image_clock.test.mjs` | 公共交互契约第11节、图片模块；认可的图片计时布局统一复用，各业务提供持久时间，终态固定及定时器清理；图片时间落库仍见 `h3ui/image_studio/runner.py` |
| 视频工作区视觉层级 | `static/studio/styles/workbench.css`、`app/workspace-controller.js` 的 `workspace-draft-note`（同在 static/studio/） | 公共交互契约第11节；提示/进度/工具栏沿用工作区边框、圆角和控件尺度，原功能分布保留 |
| 公共工作区、控件与样式 | `static/studio/ui/workbench.js`、`ui/primitives.js`、`styles/workbench.css`（后两者在 `static/studio/`） | [前端结构](docs/frontend/README.md)、[美术来源](docs/image-assets-art.md) |
| 视频制作参数呈现 | `static/studio/features/workflow-settings/index.js`、`static/studio/core/capability-client.js` | [公共交互契约](docs/frontend/parameter-and-interaction-contract.md)、[唯一详细参数映射](docs/frontend/parameter-map.md) |
| 图片制作参数与共用对话框 | `static/studio/features/image-settings/index.js`、`static/studio/ui/production-settings.js`、`static/studio/core/image-catalog.js` | 公共交互契约、参数映射；任务临时副本与当前工具恢复默认、公共顶部入口/呈现和运行中 API 契约校验各负其责 |
| API 与原始错误反馈 | `static/studio/core/api-client.js`、`static/studio/ui/error-feedback.js` | 公共交互契约、[前端结构](docs/frontend/README.md) |
| 视频工作流、字段、编译 | `h3ui/studio_capabilities.py`、`h3ui/studio_recipes.py`、`h3ui/studio_source.py`、`h3ui/studio_sources/` | [工作流适配](docs/governance/workflow-evolution-contract.md)、参数映射 |
| 视频规划、长片、尾部与声画 | `h3ui/studio_plan.py`、`studio_story.py`、`studio_tail.py`、`studio_media.py`、`segmenter.py`（均在 `h3ui/`） | 模块约定、[前端业务说明](docs/frontend/README.md) |
| 视频保存、动作与进度 | `static/studio/core/project-session.js`、`project-commands.js`、`progress-channel.js`、`export-lifecycle.js`（均在同一 `core/`） | 前端结构 |
| 图片五工具、后端、编译、恢复 | `h3ui/image_studio/{parameters,service,store,compiler,runner,inputs,routes}.py`、`h3ui/image_studio/sources/` | 图片模块、工作流适配、参数映射；text原生文字适配从原单图链派生，原四编辑分支保留 |
| 模型发现、引擎目录 | `h3ui/generation/local_models.py`、`catalog.py`；`h3ui/image_studio/service.py` | [模型目录](docs/local-model-catalog.md)、公共交互契约；图片复用本地扫描并区分远端节点缓存 |
| 资产、引用、本地任务 | `h3ui/asset_library/`、`h3ui/generation/asset_adapter.py`、`h3ui/local_tasks/`、`h3ui/jobs.py`、`static/studio/features/asset-picker/` | [资产结构](docs/asset-library-architecture.md)、[使用与维护](docs/asset-library-maintenance.md) |
| 全局当前队列与精确停止 | `h3ui/task_center.py`、`h3ui/comfy.py`、`static/studio/features/task-center/index.js`、`static/studio/styles/task-center.css`；`tests/test_task_center.py`、`tests/studio_task_center.test.mjs`、`tests/task_center_ui_fixture.py` | [当前任务队列](docs/task-queue.md)；活动记录汇总、按任务归属停止、待确认占用与隔离检查 |
| 四模式候选/运行记录整理 | `h3ui/studio_records.py`、`static/studio/ui/candidate-records.js`、图片 workspace-view/controller、视频 production/review；`tests/test_candidate_records.py`、`tests/studio_candidate_records.test.mjs` | [候选记录整理](docs/candidate-records.md)；移除/恢复元数据，保留原文件和引用，当前选用及未结束记录保护 |
| 统一分类回收站 | `h3ui/studio_recycle.py`、`static/studio/pages/asset-library/recycle-bin.js`、`styles/library.css`（同在 static/studio/）；`tests/test_recycle_bin.py`、`tests/studio_recycle_bin.test.mjs` | [分类回收站](docs/recycle-bin.md)；只读汇总三类，复用原恢复API，不迁数据 |
| 历史项目与可恢复删除 | `h3ui/projects.py`、`h3ui/routes.py`、`h3ui/studio.py`、`static/studio/pages/archive.js` | [项目档案](docs/project-archive-deletion.md)、维护基线兼容区 |
| 新增功能共同体验准入 | `docs/frontend/experience-contract.json`、`tools/check_experience_contract.mjs`、`tests/experience_contract.test.mjs` | [接入规则与场景记录模板](docs/frontend/experience-admission.md)；新增页面/动作同样评审，结构检查不等于体验验收，五模式历史缺口继续保留 |
| 上下文更新与漂移检测 | `tools/context_guard.py`、`tools/test_context_guard.py`、`docs/governance/context-check.json` | [持续维护](docs/governance/context-maintenance.md) |
| 图片参数、保存、绑定与隔离界面检查 | `tests/test_image_text_generation.py`、`tests/test_image_task_discard.py`、`tests/test_image_result_actions.py`、`tests/test_image_parameters.py`、`tests/test_image_studio.py`、`tests/test_image_api_ui_contract.py`、`tests/studio_parameter_dialog.test.mjs`、`tests/studio_image_interactions.test.mjs`、`tests/studio_image_catalog.test.mjs`、`tests/image_parameter_ui_fixture.py` | [检查与交付](docs/governance/checks-and-release.md)、维护基线；真实图片 API 临时数据模式及缺契约回归，检查种类不等于已运行结果 |
| 网站维护重载与启动恢复边界 | `tests/test_startup_recovery.py`；`run.py`、`h3ui/__init__.py`、`h3ui/studio.py`、`h3ui/local_tasks/__init__.py` | 检查与交付；启动健康信息固定报告图片参数契约及恢复标记，重载不改任务记录或唤醒旧队列 |
| 相关检查、代码分发 | `tests/`、`tools/check_repository.py`、`requirements.txt`、`config.example.json` | [检查与交付](docs/governance/checks-and-release.md)、[Git 分享](docs/github-sharing.md)、[第三方来源](THIRD_PARTY_NOTICES.md) |

上表简写路径不要求搬动代码。前端依赖方向保持 `app → modes/features → core/contracts/ui`；核心不导入具体模式、不跨模式取内部状态。图片与视频保留各自会话与保存作用域，公共呈现应复用适合的组件。

新增隐藏字段走参数映射和交互契约；新增同用途工作流走工作流适配；仅独立新任务才走 [adding-a-mode](docs/frontend/adding-a-mode.md)。地图、入口或公共组件位置改变时，同批更新本表、AGENTS 路由与检查配置。

静态资源版本证据来自 `static/index.html` 的 `app.js` 与 `style.css` 查询参数；它不是 API、数据格式版本，也不是指导包 V4。工具配置记录这个来源。历史方案在维护基线所指的外部归档，按需查证，不默认载入为待办。

入口美术：`static/assets/modes/`；视频接续使用 `mode-video-continuation.webp`，统一注册在 `static/studio/app/mode-registry.js`。风格、来源与提示词见[美术资源](docs/image-assets-art.md)。

发布入口：[相对v6.3.20的更新日志](CHANGELOG.md)、[代码与配套分发](docs/release-distribution.md)。v6.3.32使用同版GitHub Release配套包附件，版本引用与发行说明统一在更新日志中；公开版本沿用既有main历史，不合入原维护仓库历史。

资产跨模式覆盖及可维护性：[2026-09-08审查](docs/asset-system-audit-20260908.md)。原报告保留为修复前证据；[6.3.21整改](docs/asset-system-improvements-20260908.md)记录公共使用登记、图片转入续写段、批量查询和前端职责拆分。历史漏记不自动回填，绑定包/版本更新仍按模式适配。

资产整改定位：`h3ui/asset_library/usage.py` 统一项目提交后的使用登记；`features/asset-picker/{destinations,assembly-use}.js`（位于 static/studio/）声明图片转入位置及续写段确认。资产页 `pages/asset-library/{batch-actions,input-dialog,media-timeline}.js` 分别承接批量操作、输入弹窗、选段预览；列表/详情保留页面状态与重绘。相关检查：tests/test_library_usage.py、tests/studio_library_usage.test.mjs、tests/library_transfer_ui_fixture.py。

UI、UX与代码复用现状：[6.3.21静态审查](docs/ui-code-reuse-audit-20260908.md)。列出现有公共层、三套页头/步骤模板、部分错误/底栏未接入、参数内部组合及候选/播放等重复，并划定保存/生成/媒体业务不能强并的边界；这是后续实施依据，不表示新重构已经完成。

跨模式体验完善的最新目标：[体验一致性方案](docs/product/experience-consistency-plan.md)。用户要求同一操作习惯贯穿五模式；以动作语义、位置、状态反馈及用户操作脚本验收，代码复用服务于体验。本地6.3.23已落地首批参数/保存与离开保护及第二批页头/步骤/底栏，候选与异步批次未完成；上一轮静态审查保留为修复前证据。

第三批结果体验：`static/studio/ui/result-view.js`统一候选状态与结果动作，`ui/media-player.js`统一四视频播放生命周期，`ui/candidate-records.js`含接续恢复适配（均位于static/studio）。调用方为features/production、image-results、export与modes/video-assembly；成功入库回执适配在features/asset-picker/result-import.js。检查入口`tests/studio_result_experience.test.mjs`、`tests/result_experience_ui_fixture.py`；实际范围与待办见[第三批交付](docs/frontend/experience-phase3.md)。

第四批异步入口：`static/studio/core/{async-state,progress-channel,task-state,upload-client}.js`、`static/studio/ui/async-feedback.js`；真实入库回执由`h3ui/asset_library/results.py`和`store.py`读取既有operations，routes.outputs声明契约。检查`tests/studio_async_experience.test.mjs`、`tests/test_result_receipts.py`、`tests/async_experience_ui_fixture.py`；接入与边界见[第四批交付](docs/frontend/experience-phase4.md)。


资产共同体验与来源追溯：后端`h3ui/asset_library/{origins,generation_records}.py`；前端`static/studio/ui/{asset-origin,source-parameters}.js`及`features/asset-picker/origin-view.js`。详情与选择器共用，各模式素材提供固定version/media链接。原接续source_parameters保留适配转调。检查`tests/test_asset_origins.py`、`tests/studio_asset_origins.test.mjs`、`tests/asset_origin_ui_fixture.py`；范围及边界见[6.3.26交付](docs/asset-experience-20260908.md)。

来源记录定位：`static/studio/core/source-target.js`校验origin_*身份；`ui/source-navigation.js`提供共同反馈，三个workspace控制器适配五模式只读查看位置。检查`tests/studio_source_target.test.mjs`和`tests/source_navigation_ui_fixture.py`；见[6.3.27交付](docs/asset-source-navigation-20260908.md)。

资产添加/管理共同入口：`ui/reference-metadata.js`提供用途意图确认；`features/assets`、接续references与库转入适配。原三视频草稿与库引用联合预览归`asset_library/project_import.py`，能力在库catalog发布。五模式实际添加/管理检查`tests/asset_lifecycle_ui_fixture.py`；源视频草稿冲突`tests/test_asset_import_draft.py`。三阶段总进度见[6.3.28交付](docs/asset-lifecycle-20260908.md)。

派生链与已入库下游：`h3ui/asset_library/{lineage,descendants}.py`由origins/routes接入；前端复用`ui/asset-origin.js`及`features/asset-picker/{origin-view,descendants-view}.js`。lineage只读冻结身份，descendants按需分页元数据；不从refs推导派生。检查`tests/test_asset_lineage.py`与`tests/asset_lineage_ui_fixture.py`，当前范围和剩余第三阶段工作见[6.3.29交付](docs/asset-lineage-20260909.md)。

运行来源身份：`h3ui/generation/source_lineage.py`由studio.generate_one和studio_story.generate_story调用，TaskStore传外层父身份与内部归属；Results保留入库元数据。`asset_library/generation_descendants.py`只读分页项目结果，复用lineage，前端descendants-view按作用域配置。测试`tests/test_runtime_lineage.py`及已扩到五模式的`tests/asset_lineage_ui_fixture.py`；现状见[6.3.30](docs/asset-runtime-lineage-20260909.md)。

素材包跨库来源：`h3ui/asset_library/pack_lineage.py`负责明确身份、包内校验、导入映射和旧包媒体隔离；`packs.py`负责格式2往返（兼容读取1），`store.save(fixed_receipt=True)`只用于新版包固定版本回执。`pages/asset-library/transfer.js`提供来源勾选与预览代次保护，公共来源/下游模板不复制。检查`tests/test_pack_lineage.py`、`tests/asset_pack_lineage_ui_fixture.py`；[6.3.31交付与总进度](docs/asset-pack-lineage-20260909.md)。

统一提示词库（本地6.3.32）：[现行使用、配置、接口与检查](docs/prompt-library.md)，[V3执行账本](docs/product/prompt-library-execution-plan.md)的P1～P5完成。独立后端h3ui/prompt_library处理分类/版本/已保存快照补记/生成记录；前端features/prompt-library处理共同管理与五模式适配，ui/prompt-editor.js只负责公共呈现，pages/prompt-library为全局工具页。保存入口覆盖原视频apply和独立draft、图片apply、接续save及asset_library/project_import联合提交。实际主模型来源元数据归families.py及可选prompt_model_families配置，H3/Krea2不按变体或辅助组件拆分；未知不阻止保存。测试入口tests/test_prompt_library.py、tests/prompt_library_ui_fixture.py及tests/test_asset_import_draft.py。新功能的公共接入按现行准入表执行，未来剧本/LLM仍待独立业务方案。
