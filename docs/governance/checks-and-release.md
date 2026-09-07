# 相关检查、交付与分享

检查按本次影响选择，保留既有隔离用例。默认不运行 ComfyUI、不调用真实 `/prompt`、不加载模型、不测画质/显存/速度或参数组合。结构检查通过不表示实际生成成功。

## 阶段 A 检查边界（已交付）

仅核对现行入口、规则冲突、真实源码位置、文档链接和维护工具；运行上下文工具的临时资料自检，以及内容复核后的 record/check。不启动网站、不导入应用、不运行全站测试。历史报告的检查数不能写成本轮成绩。

```powershell
# 从真实仓库根目录使用已有 Python；此处不安装依赖
.\.venv\Scripts\python.exe tools/test_context_guard.py
.\.venv\Scripts\python.exe tools/context_guard.py check --root .
```

record 的前提、顺序及命令见 [持续维护](context-maintenance.md)。新会话开始先 check 一次，交付前同步内容后再 record/check；禁止为通过检查直接刷新指纹。

## 仅视觉样式调整

沿用真实组件生成隔离静态样例，用本机已有无界面浏览器渲染受影响模式与宽窄窗口，核对边框/字号/容器间距和横向溢出。只读实际CSS与渲染模块，独立浏览器资料目录，不使用生产API、真实媒体或生成。样例无事件绑定时必须说明未覆盖实际点击与保存；无需为可逆CSS微调添加镜像式单元测试。相关语法/既有回归按影响选取，证据记录在维护基线。

## 公共计时呈现检查

`node --test tests/studio_run_timing.test.mjs tests/studio_image_clock.test.mjs tests/studio_frontend.test.mjs tests/studio_candidate_records.test.mjs`：四模式实际呈现函数使用同一计时块，核对准备/合成、终态固定、缺时间/未确认、原图片等待与排队、每秒文本更新和销毁。仅前端调整时不运行生成或全站后端测试。纯函数验证不能代替实际页面视觉验收。

## 图片文生图分支

`.\.venv\Scripts\python.exe -m unittest tests.test_image_text_generation tests.test_image_parameters tests.test_image_studio tests.test_image_api_ui_contract tests.test_image_task_discard tests.test_image_result_actions -q` 和 `node --test tests/studio_image_interactions.test.mjs tests/studio_image_catalog.test.mjs tests/studio_parameter_dialog.test.mjs`。临时真实API检查无A/B保存、缺描述拒绝、尺寸与五工具字段、固定种子0、原生加载/文本编码/采样图绑定、合成输出接收/入库/继续编辑，节点声明使用替身。原四分支比较修改前后的完整编译图与geometry，保护默认及非默认连接。

隔离浏览器实际点击参数取消/快速重开/应用/保存、文生图检查输入、两次追加候选、快捷入库、结果转单图及切回原文字任务。生成路由由本地替身接收并写合成候选，核对已保存参数/revision/不同key，不调用runner或ComfyUI；参数关闭事件回归需确保旧close事件不误关新弹窗。核对宽窄页面/参数截图，真实生成仍待用户。生产只读查看catalog.text_to_image_version，缺失时明确后台尚未加载；不以静态版本代替。

## 图片重复生成、默认恢复与快捷入库

`node --test tests/studio_parameter_dialog.test.mjs tests/studio_image_interactions.test.mjs tests/studio_image_catalog.test.mjs tests/studio_frontend.test.mjs` 与 `.\.venv\Scripts\python.exe -m unittest tests.test_image_result_actions tests.test_image_api_ui_contract tests.test_image_parameters tests.test_image_studio tests.test_candidate_records -q`：默认值读取当前工具真实API，取消/应用/保存及四工具离线编译；快捷入库保留选用、来源和幂等，原第三步选用兼容。浏览器用临时Flask/SQLite和合成媒体，实际点击重新生成时仅隔离替身接收请求，核对原任务/原图/revision/key和保存顺序，不能提交给runner或引擎。核对第二步返回、快捷收藏不切页、默认取消/应用/保存，以及宽窄操作布局。生产服务只读核对catalog.quick_ingest_preserves_selection；缺标记明确待重启，不自动重载用户页面。

## 图片编辑任务废弃检查

`.\.venv\Scripts\python.exe -m unittest tests.test_image_task_discard tests.test_image_result_actions tests.test_candidate_records tests.test_recycle_bin tests.test_image_studio -q` 和 `node --test tests/studio_image_interactions.test.mjs tests/studio_recycle_bin.test.mjs tests/studio_candidate_records.test.mjs`。真实临时API检查废弃/恢复、零任务后新增保存、旧计划/旧草稿拒绝、原媒体/资产/快照保留、选用清除、父项目与单独移除候选分离；浏览器实际点击取消/确认、切换剩余任务、清空、新增保存和回收站恢复。只读核对运行后台catalog.task_discard_version，不在生产任务上试废弃、不以生成或中断验证保护。

## 分类回收站检查

`.\.venv\Scripts\python.exe -m unittest tests.test_recycle_bin tests.test_candidate_records tests.test_image_studio tests.test_task_center -q` 与 `node --test tests/studio_recycle_bin.test.mjs tests/studio_candidate_records.test.mjs tests/studio_frontend.test.mjs` 使用临时数据/假引擎。包含真实API→JS恢复请求→原恢复API的桥接，分类只读、父项目/候选恢复分离、分页、搜索及版本/占用保护。浏览器检查应使用同样隔离的完整路由，验证分类切换、取消、逐条恢复及资产批量恢复；不得用生产记录验收。

## 候选移除与恢复检查

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_candidate_records tests.test_image_studio tests.test_task_center tests.test_image_run_clock -q
node --test tests/studio_candidate_records.test.mjs tests/studio_image_clock.test.mjs tests/studio_image_interactions.test.mjs tests/studio_frontend.test.mjs
```

仅临时数据和假引擎。覆盖移除/恢复、当前选用保护、项目版本/归属、未确认占用、旧入库令牌、文件与快照保留；图片 API→实际 JS→保存重读桥接不等于浏览器验收。不在生产记录上验证移除。

## 后续开发如何选检查

全局任务队列新增隔离入口：`python -m unittest tests.test_task_center -v`、`node --test tests/studio_task_center.test.mjs`。前者从真实工厂使用临时配置、两类数据库与假引擎，验证列表只读、当前队列过滤、精确取消、网络/归属失败、完成竞态、未知关闭、worker lease、视频内部停止边界；不得在生产队列上点击停止来验证。`tests/task_center_ui_fixture.py --port 5098` 提供同样隔离的真实 HTTP/静态页面。浏览器工具不可用时应明确未完成页面点击/视觉验收，不能以 HTTP 或纯函数检查冒充。

阶段 B 及图片反馈修复允许使用真实组件的隔离页面、真实图片 API 与临时数据检查保存和离线图绑定；模拟接口仅用于界面状态检查。仍禁止 ComfyUI、真实生成、生产数据试写或自动安装升级。下表按实际影响选取，不重复阶段 A 或全站检查。

| 变更 | 必要的相关非生成检查 |
|---|---|
| 小参数或新增字段 | 非默认值、取消/应用、保存重开、normalize/compile 落点、旧缺省行为 |
| 同用途新工作流 | 原模块选择器、有效字段/输入、绑定、审核/合成/资产接续及切换影响 |
| 公共 UI | 受影响模块路径、各自草稿/作用域、相关视口和空/失败/长内容状态 |
| 状态或错误处理 | 模拟拒绝/运行错误、摘要及原始错误、素材/草稿/旧结果保留、未知提交不自动重发 |
| 依赖变化 | 沿用维护基线：三视频、图片受影响路径、资产、历史读取、保存/审核/合成的兼容检查 |

不因单字段修改重复全站截图或排列组合。文件发现可使用隔离假文件，但不加载权重。现有 `tests/` 中部分用例依赖本机配置、节点缓存、FFmpeg 或历史断言，执行前查看具体用例，不能把整个目录直接变成发布 CI。普通网站启动会组装服务并可能唤醒已登记任务，不能用生产配置启动来做无副作用探查。

现有前端无 Node 构建步骤；相关 Node/Python 用例入口见 [README](../../README.md) 和 [前端说明](../frontend/README.md)。不虚构 `npm test`，不以旧报告代替本轮验证。

## 图片参数阶段 B 的检查入口

实际检查结果及证据只记在[维护基线](../maintenance-baseline.md)。以下入口使用隔离数据；真实 API fixture 不导入完整应用工厂，启动恢复用例则将工厂指向临时配置并阻断引擎网络和 worker。离线 compile_graph 仅验证参数进入实际图。

```powershell
node --test tests/studio_parameter_dialog.test.mjs tests/studio_image_interactions.test.mjs tests/studio_image_catalog.test.mjs tests/studio_frontend.test.mjs tests/studio_asset_modes.test.mjs
.\.venv\Scripts\python.exe -m unittest tests.test_image_parameters tests.test_image_studio tests.test_image_api_ui_contract tests.test_startup_recovery -v
```

`tests/image_parameter_ui_fixture.py --real-image-api --port 5098 --evidence-dir <外部目录>` 使用真实图片 Flask 路由、ImageStudio 和临时 SQLite；真实 LocalModels 只扫描隔离假文件。catalog 原样进入前端，不补造参数字段。三视频对照仍为模拟 API。未指定 real-image-api 时保留原合成 API 模式，用于刷新失败、保存冲突及预置运行错误；两种模式均拒绝生成／引擎调用。预置候选和种子不代表生成。只在授权的相关页面检查中启动，结束即退出，不替换真实网站。

### 实际运行服务的契约与维护重载

`run.py` 不热重载 Python；`start.bat` 发现 5093 已监听时仅打开浏览器。当前磁盘代码与静态文件不能证明旧后台已更新。修改图片参数契约时核对已运行网站的只读 `/api/v5/health`（启动时固定的 `image_parameter_contract_version`）及 `/api/v5/image-projects/catalog`（版本 1 和四工具真实描述）。缺失时前端应提示网站版本不匹配，模型刷新失败保留原目录和参数草稿。

在实际修复需要且授权覆盖的情况下，仅重载确认空闲的网站进程。维护命令为 `.\.venv\Scripts\python.exe run.py --no-browser --no-startup-recovery`：跳过视频旧状态重写、资产本地任务重置、图片／资产 worker 唤醒和视频自动恢复；配置不回写，之后用户主动操作保持原样，普通启动默认恢复仍保留。重载前后核对受保护配置和数据库记录，确认健康接口 `startup_recovery=false` 且图片契约已加载；不刷新用户未保存页面或用生产项目试写。不以“busy=false”推断持久队列不存在，也不为验证调用在线节点同步。

本轮没有重新跑阶段 A 的57次工具自检。上下文工具本身未改；开始 check、同批内容复核后的 record/check 与本轮业务用例分开说明。

## 交付完成条件

- 本次授权范围完成，真实差异已记录，保留认可体验和用户数据。
- 列明实际做过的相关非生成检查；真实生成、性能和用户体验验收分别标状态。
- 对应专业文档、唯一当前状态、地图和 AGENTS 必要正文/路由同批同步；稳定内容不需改时说明理由，索引在内容复核后刷新并检查。
- 有提交授权时代码与文档同提交/PR；没有就同一工作树交付，不自动提交、推送或发布。
- 提供局部撤回方式；Git 只能恢复代码，不能用旧数据库覆盖新作品。

上下文检查通过不替代业务检查。没有真实生成可以交付文档/代码接入或非生成检查结果，不能说任意模型组合、16GB 峰值或长链质量已验证。

## Git 与分发

唯一现行 Git 操作边界见 [github-sharing.md](../github-sharing.md)。保留原 Git 历史和远程，用户未授权不更改远程、不公开推送。原 `origin` 是既有镜像，不直接把它当作发布目标。

`python tools/check_repository.py` 检查 Git 暂存区的运行/私密路径、明显凭据、大文件和 JSON，不覆盖未暂存改动；只在实际涉及暂存/分享检查时使用。它不会执行上下文语义复核。本轮不为了让它看到文件而擅自暂存。

分享应保留有分发依据的必要代码、公共组件、工作流、示例配置、依赖说明、现行规范、AGENTS 与检查工具。真实配置、数据库、作品、外部资产、权重、环境和私有日志继续排除。[第三方来源](../../THIRD_PARTY_NOTICES.md) 的许可边界继续有效，网站 MIT 不覆盖所有外部内容。

未配置钩子/CI 时由维护任务调用工具；未来接入需相应授权，只接 `check`，不自动重记快照。发布审查集中在发布任务执行，不给日常换模型/改参数增加认证流程。

## 视频拼接隔离检查

`python -m unittest tests.test_video_assembly -q`覆盖真实临时API、两配方默认/非默认图绑定、固定0种子、后台进度与独立草稿、混合声画/尺寸/FPS/VFR/方向媒体导出、外部尾部、子进程取消、未知提交/归属保护、入库和恢复。实际FFmpeg仅使用测试生成的纯色和测试音，不读用户作品；ComfyUI方法默认禁止，运行回收检查使用替身。

`node --test tests/studio_video_assembly.test.mjs tests/studio_task_center.test.mjs tests/studio_recycle_bin.test.mjs tests/studio_run_timing.test.mjs tests/studio_frontend.test.mjs tests/studio_parameter_dialog.test.mjs`核对公共调用和纯交互逻辑。

`python tests/video_assembly_ui_fixture.py --evidence-dir <仓库外证据目录>`使用现有Chrome无界面模式和真实临时API，检查宽窄布局、参数切换/取消/默认/刷新/保存、排序、纯拼接、入库及多选取消/应用。生产进程加载与真实生成另行记录，本轮不发布GitHub。

6.3.13公共界面回归新增tests/shared_ui_fixture.py（原三视频模拟API、图片真实隔离API），拼接tests/video_assembly_ui_fixture.py增加同级导入、主按钮次序、素材上传/用途/保存/沿用/移除及参数根样式检查。对应后端测试含双图参考+尾部绑定和替身执行输入复制。用外部evidence-dir，既有Chrome与临时数据；不连接生产引擎。通过数量与证据见维护基线。
