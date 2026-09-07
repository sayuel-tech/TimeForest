# 时间森林项目地图

唯一维护来源：`<仓库根目录>`。当前状态与交接只写在 [维护基线](docs/maintenance-baseline.md)，长期规则与读取顺序见 [AGENTS](AGENTS.md)。本文件只定位代码和现行说明，不另维护版本台账或参数表。

按用户功能定位；同用途新工作流加到原模块。家族级代码复用可以继续，模型世代变化不自动成为新增页面或模块的理由。

| 工作内容 | 真实实现入口（相对仓库根目录） | 现行说明 |
|---|---|---|
| GitHub代码与独立工作流包 | 当前源码筛选导出；六个原始工作流、五个图片API示例与模型TXT独立压缩 | [独立分发](docs/release-distribution.md)含网盘下载入口与提取码；保留原维护历史，公开快照排除工作流/模型清单包/个人资料，补包后离线验证 |
| GitHub项目介绍与功能表述 | `docs/project-introduction.zh-CN.md`、`docs/images/`、`docs/product/tool-comparison.md`；公开README同步图文，原维护README保留安装入口 | [GitHub分享](docs/github-sharing.md)；正式介绍以视觉设计和交互体验开篇，再说明四模式、迭代制作与资产复用；生成效果和硬件能力按真实证据表述 |
| 启动、组装与页面 | `start.bat`、`run.py`、`h3ui/__init__.py`、`static/index.html`、`static/studio/app.js` | [README](README.md)、[维护基线](docs/maintenance-baseline.md)；`--no-startup-recovery` 仅抑制本次启动恢复，默认行为不变 |
| 桌面菜单与网站启动停止 | `tools/director-menu.cmd`、`tools/director_service.ps1`、`tests/director_service.tests.ps1`；桌面 `启动时间森林导演台.cmd` 为绝对路径转接 | [启动停止菜单](docs/director-launcher.md)；复用当前配置与现有环境、准确进程核对、隐藏运行及本地日志 |
| 功能导航、三个视频工作区 | `static/studio/app/mode-registry.js`、`static/studio/modes/{swap,image-story,text-story}/workspace.js` | [模块约定](docs/product/module-contracts.md)、[前端结构](docs/frontend/README.md) |
| 图片工作区与任务 | `static/studio/app/image-workspace-controller.js`、`core/image-session.js`、`features/image-results/workspace-view.js`、`features/image-canvas/index.js`（后三者均在 `static/studio/`） | [图片模块](docs/image-assets.md)、[图片 UI](docs/frontend/image-workspace-ui.md)；任务废弃/恢复在 `h3ui/image_studio/service.py`/`routes.py`，零任务空态保留新增入口 |
| 四模式公共计时与运行时间 | `static/studio/ui/run-timing.js`、`ui/primitives.js`；图片 workspace-view、视频 production/records、source-preparation、export（均在 `static/studio/`）；`tests/studio_run_timing.test.mjs`、`tests/studio_image_clock.test.mjs` | 公共交互契约第11节、图片模块；认可的图片计时布局统一复用，各业务提供持久时间，终态固定及定时器清理；图片时间落库仍见 `h3ui/image_studio/runner.py` |
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
| 上下文更新与漂移检测 | `tools/context_guard.py`、`tools/test_context_guard.py`、`docs/governance/context-check.json` | [持续维护](docs/governance/context-maintenance.md) |
| 图片参数、保存、绑定与隔离界面检查 | `tests/test_image_text_generation.py`、`tests/test_image_task_discard.py`、`tests/test_image_result_actions.py`、`tests/test_image_parameters.py`、`tests/test_image_studio.py`、`tests/test_image_api_ui_contract.py`、`tests/studio_parameter_dialog.test.mjs`、`tests/studio_image_interactions.test.mjs`、`tests/studio_image_catalog.test.mjs`、`tests/image_parameter_ui_fixture.py` | [检查与交付](docs/governance/checks-and-release.md)、维护基线；真实图片 API 临时数据模式及缺契约回归，检查种类不等于已运行结果 |
| 网站维护重载与启动恢复边界 | `tests/test_startup_recovery.py`；`run.py`、`h3ui/__init__.py`、`h3ui/studio.py`、`h3ui/local_tasks/__init__.py` | 检查与交付；启动健康信息固定报告图片参数契约及恢复标记，重载不改任务记录或唤醒旧队列 |
| 相关检查、代码分发 | `tests/`、`tools/check_repository.py`、`requirements.txt`、`config.example.json` | [检查与交付](docs/governance/checks-and-release.md)、[Git 分享](docs/github-sharing.md)、[第三方来源](THIRD_PARTY_NOTICES.md) |

上表简写路径不要求搬动代码。前端依赖方向保持 `app → modes/features → core/contracts/ui`；核心不导入具体模式、不跨模式取内部状态。图片与视频保留各自会话与保存作用域，公共呈现应复用适合的组件。

新增隐藏字段走参数映射和交互契约；新增同用途工作流走工作流适配；仅独立新任务才走 [adding-a-mode](docs/frontend/adding-a-mode.md)。地图、入口或公共组件位置改变时，同批更新本表、AGENTS 路由与检查配置。

静态资源版本证据来自 `static/index.html` 的 `app.js` 与 `style.css` 查询参数；它不是 API、数据格式版本，也不是指导包 V4。工具配置记录这个来源。历史方案在维护基线所指的外部归档，按需查证，不默认载入为待办。
