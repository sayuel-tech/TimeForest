# 资产库与引擎适配结构

分类回收站是现有移除标记的只读汇总视图：`studio_recycle.py` 读取库deleted、项目deleted_at及运行removed_at；恢复沿用各原接口，不新增库表、迁移文件或复制项目。资产库中的版本/引用结构保持。详见[分类回收站](recycle-bin.md)。

## 模块职责

| 模块 | 职责与不能做的事情 |
|---|---|
| `asset_library/store.py` | 独立SQLite、索引、资产身份、不可变版本、分类合集及修订号；不访问ComfyUI |
| `service.py`、`media.py`、`uploads.py` | 有界上传、原件哈希、实际媒体探测、预览与一致性备份；原件与缩略图分离 |
| `bindings.py` | 按固定版本展开媒体与归属；禁止输出资料PROMPT、设定或录音台词 |
| `generation/asset_adapter.py` | 模式输入能力注册、媒体用途、数量与声音范围；声明真实已适配节点 |
| `project_import.py` | 用临时视图预检整包引用，生成服务器计划，复制独立执行副本，原子提交项目变化；跨库引用登记幂等补全 |
| `derive.py`、`collect.py`、`results.py`、`packs.py` | 非破坏媒体处理、明确目录收集、确切候选回收和可移植包；附件工作流永不执行 |
| `local_tasks`、`jobs.py` | 持久本地任务、有限并发、项目占用及独立GPU通道 |
| `generation/catalog.py`、`launcher.py`、`recovery.py`、`drafts.py` | 离线目录、可选已核验启动、提交对账／已有任务恢复、独立运行后草稿 |
| `pages/asset-library` | 独立路由会话、资料编辑与本地工具；不借用某个项目状态 |
| `features/asset-picker` | 共用选择器、用途与变更确认、传输、项目结果回收；由模式指定输入意图 |

## 数据边界

资产ID表示创作身份，文件hash仅用于物理去重。版本存完整不可变快照，当前分类关系可独立迁移；项目保存源库ID、固定版本、媒体、用途、角色实例、绑定根与独立文件副本。已有项目不会追随库当前版本自动更新。

不可把 `record_prompt`、`description`、`provenance` 拼入 `studio_prompts`。编译只接收最终媒体、用途、角色与用户制作正文。`asset_map` 增加库版本和真实 loader／conditioning 对应，供预检与运行记录查看。

新来源类型通过入库服务提供可信文件和真实provenance。客户端只传已登记输出ID，不能传任意绝对路径作为项目结果。仅“收集目录”明确接受用户指定目录范围，并先列待选文件；不是后台监听或磁盘搜索。

## 引用的事务边界

1. 用户编排经原有命令门自动保存。
2. 选择库版本并展开绑定；用户取消／覆盖媒体、角色号和旧引用。
3. `/use-plan` 只写服务器暂存计划，不修改项目引用或复制媒体。现有变更规划器负责配方切换与旧结果影响。
4. `/use-apply` 登记幂等本地任务，持有该项目占用，复制并校验媒体到项目内；所有资产记录和项目revision在一次SQLite事务提交。
5. 库内refs与最近使用登记在项目提交后补全；若中断，重试只补登记，不重复应用变更。
6. 完成状态只在释放占用后发布，下一步源视频准备不会撞上遗留锁。

两个数据库不是一个事务。半成品文件可能留在磁盘，但不会发布为可选的坏项目记录。旧计划的revision／有效期不匹配必须重新预览。

## 增加新模式

先判断用户任务：同用途工作流应走 [原模块内适配](governance/workflow-evolution-contract.md)，新字段走 [参数映射](frontend/parameter-map.md)；只有 [模块约定](product/module-contracts.md) 无法承载的独立新任务才使用本节新增模式流程。模型家族或加载节点更新本身不构成新增模块理由，现有资产适配仍优先复用。

1. 先定义模式业务输入，向 `generation.asset_adapter.ADAPTERS` 登记可直接接收的类型、用途和容量；不支持的媒体返回明确状态。需要派生时提供已有本地工具入口，不能偷偷把声音/控制图变为文字。
2. 在配方与编译器中实现实际加载节点和对应输入，写结构用例证明参数和媒体可达最终条件节点；不能只改前端控件。
3. 模式前端调用共用 `ctx.useLibrary(segmentId, target)` 与本地上传入口。新媒体根引用使用一致的 `owner`，同角色图与声线共享subject；别的角色使用不同subject。
4. 模式输出登记真实可完成文件，项目候选与最终成片由ResultImports回收。其他输出类型新增独立注册器，复用 `Library.ingest`，不修改素材库身份规则。
5. 原件、代理、执行副本分开。新GPU工具必须注册到GPU通道，本地派生只注册LocalTasks；日常读取不能偷偷启动引擎。
6. 执行三条必要契约：取消后项目不变；资产资料修改后相同运行编译图完全相同；更新/回收库资产后旧项目副本仍可访问。

详见 `docs/frontend/adding-a-mode.md` 的模式UI生命周期。新增耗时弹窗使用 `scopedModal`，迟到任务只更新自己的内容；路由切换通过AbortSignal停止前端等待，不撤销已经登记的后台任务。

## 迁移和兼容

资产库schema从1开始，启动拒绝较新schema。项目原有表保留，仅增加独立草稿表；资产库数据不批量塞入旧项目。旧版本代码能继续读取原项目表，新增库引用已经落为常规项目媒体副本。

离线维护工具默认dry-run，禁止网站仍监听端口时迁移。复制、校验、更新缓冲路径后才切换配置；原库与旧配置保留。库历史版本默认不永久删除；仅已完成临时派生可按保留天数列明清理。

## 隔离验收

`tests/test_local_server.py` 默认拦截所有ComfyUI读取，配置明确禁止生成。

- `test_asset_library.py`：原件、身份、版本、异常、绑定、备份。
- `test_library_workflow.py`：三模式真实加载／条件节点、资料不入正文、确认取消、双角色归属、固定版本更新、无素材段。
- `test_library_media_tools.py`：29.97fps声画范围、透明图片变换、目录写入变化、便携包和路径校验。
- `test_library_recovery.py`：确切运行信息回收、单独草稿、准确提交对账、有限只读重试、本地任务完成边界、启动配置拒绝。
- `test_library_maintenance.py`：磁盘失败不切换、停站要求、迁移和恢复副本、清理白名单。
- `tools/benchmark_library.py`：临时库5000条元数据，结果是本机测量，不是各硬件性能保证。

不在普通自动检查中调用真实 `/prompt` 或装载模型。图像质量、身份、声音模仿效果及显存峰值须另行得到用户允许后核验。

## 视频拼接的输入与结果

video_assembly序列服务接受本地上传或固定asset/version/media视频ID，复用公共资产选择器可选多选，默认单选调用保持。服务核对媒体归属、创建项目副本并保存来源哈希，不走swap单源参考槽，不读资料PROMPT。结果枚举增加续接/拼接成片，快捷入库与通用项目结果导入共用来源去重键；移除父片段或续写段后先恢复父项。项目仍用现有JSON与revision，无新数据库或版本迁移。[使用说明](video-assembly.md)。

## 视频拼接续写参考

6.3.13由video_assembly/references.py接收当前固定asset/version/media，验证类型后复用Studio.upload规范化为项目副本；段内仅绑定id/用途/角色。生成快照冻结副本哈希和库来源，执行输入不动态读取资产最新版本；资料PROMPT不进入正文。选择器与卡片呈现复用ui/reference-assets，旧视频素材业务保持。

## 公共使用登记与模式适配（6.3.21）

项目提交后的公共完成入口为 `Library.complete_usage`，由 `usage.py` 统一校验固定版本媒体、写历史 refs、更新 used 并记录幂等操作。原三视频在 ProjectImport.apply 后调用；图片从输入准备移到确认 apply；接续视频与参考图/声音在项目保存后调用。项目提交成功但库登记失败的状态必须明确反馈并允许补登记，不能重新导入来掩盖失败。

历史 refs 不等于当前有效引用；used 仅成功新增引用更新，同一操作重试不刷新，旧事件不倒退。图片补登记读冻结的 image_changes；接续以项目内新导入记录的 library_used_at 和媒体 ID 为凭据。旧版本缺失的时间不补造，不在启动时批量改写历史数据。原三视频的绑定展开/检查新版不自动扩展到图片 A/B 或接续逐项引用。

列表用 LibraryStore.objects 批量读取去重媒体，分类查询也批量化；public 单项调用保持兼容。图片结果转入由 destinations 声明真实目标，接续需选择已有续写段，原三视频仍走分镜预览/确认链。前端批量整理、简单输入、媒体选段从列表/详情分离，页面继续拥有加载与草稿状态。

完整改动、失败恢复、检查和历史局限见[审查整改](asset-system-improvements-20260908.md)；[原审查](asset-system-audit-20260908.md)保留修复前证据，不再作为当前缺口列表。


## 公共来源解析（6.3.26）

AssetOrigins按确切资产版本和媒体读取来源；生成项目、父资产链、历史使用项目分离。generation_records集中解析保存的图片/视频参数，旧接续入口转调。展示和请求分层，避免公共ui依赖模式内部或资产请求模块。接口、16层派生限制及兼容见[共同体验交付](asset-experience-20260908.md)。不更换库身份或表，不用当前项目参数填历史。

素材与页面草稿联合确认（6.3.28）：ProjectImport.plan的可选draft经原Studio.edit_plan与PreviewStore只读校验，use-apply沿既有changes令牌提交。ProjectImport只组合已有规划结果，不另建保存规则；检查/取消不更新项目、refs或used，确认后的使用登记继续complete_usage。前端意图收集归ui/reference-metadata.js，业务目标和上传归各适配。详见[本批交付](asset-lifecycle-20260908.md)。

## 派生链与反向查找（6.3.29）

lineage.py按冻结身份读取资产/图片输出/接续运行，逐分支限定16层、单次64项；图片只认执行输入，不认可能残留的任务parent_output。descendants.py复用它，按versions既有rowid上界及media索引分页，每批25项，查询已入库后继的历史版本。接口`GET /assets/<id>/descendants`要求version/media，后续传回cursor/upper；不使用refs、不改库表、不读生成媒体内容。前端详情/选择器共用按需展开与重试。类型、旧元数据边界及检查见[本批交付](asset-lineage-20260909.md)。

## 运行来源与项目结果下游（6.3.30）

source_lineage由真实生成入口旁路写入候选/manifest，捕获resolve/inventory与前一选用身份，内部任务保留外层归属；不进入编译参数。lineage支持原视频候选及历史编排只读解析。generation_descendants查询五模式项目生成记录和当前成片，不要求先入库，不写operations/refs或项目；ResultImports仍沿原登记/入库流程携带source_lineage。两个下游视图共用分页模板，作用域与是否入库分开。接口、时间截止/稳定身份游标、旧记录边界见[6.3.30交付](asset-runtime-lineage-20260909.md)。

## 素材包身份边界（6.3.31）

pack_lineage集中实现media_origin、导出固定关系、联合依赖验证和接收库映射。包格式2的media.portable_lineage声明包内/包外来源，来源关系独立于可选工作流资料；保留导出时已经选择的资产集合，不沿追溯链自动打包。真实站点导出复用AssetLineage读取已经记录且可核对的上游；纯Library调用仅提取可直接确认的固定引用，并明确不完整状态。

导入仍经原Packs/local_tasks和LibraryStore，不迁库。included引用匹配发送方asset/version/media/hash，导入后改写为接收方固定身份；outside只显示外部记录。来源与绑定共同构成导入依赖，先校验循环；版本2导入幂等回执同时记录首次asset/version，部分失败后重试也不指向后来编辑的版本。旧包仍可读，旧实现残留的每媒体来源由media_origin隔离，外部项目不跳本机同编号项目。公共lineage/descendants继续承担来源和反查，generation_records有界解包只读参数，不自动应用。

包内关系是清单提供并经媒体摘要核对的声明，不是作者身份签名认证；包外项目/候选不自动迁移，旧数据不补造。具体兼容、验证与用户操作见[交付说明](asset-pack-lineage-20260909.md)。


## V3.0 剧本与电影接入

creation/reference、handoffs、movie 通过原 library fixed version/usage/ingest 接入。电影单段与成片保存固定输入来源、实际生成快照和原项目 ID，lineage/生成反查扩展读取 movie_takes 与 export parts；不查询当前采用来推断旧视频来源。素材包仍走原包内映射和外部身份边界，不新建资产体系。
