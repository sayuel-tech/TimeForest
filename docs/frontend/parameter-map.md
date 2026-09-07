# 参数从页面到执行图

本文件是前端到持久字段和执行图的唯一详细映射说明，事实以真实 normalize / compile 为准；名称、分组、作用域及取消／应用行为见[统一参数与交互契约](parameter-and-interaction-contract.md)。新工作流先走[工作流适配契约](../governance/workflow-evolution-contract.md)，不另建平行参数表。

视频权威来源是 `h3ui/studio_recipes.py` 的 Recipes 注册及 normalize / compile、`h3ui/studio_capabilities.py` 的能力声明。视频 UI 读取各 recipe 的 parameters、capabilities，按 when 隐藏无效字段；保存使用 change-plan → 必要影响确认 → apply；生成使用已保存配置。预检图与实际提交图分开提供下载。图片来源和作用域见下文“图片任务映射”；图片与视频共用 `static/studio/ui/production-settings.js` 的参数外壳、分类导航及控件，业务草稿和保存作用域分别保留。

## 视频项目与片段映射

下表采样／模型字段属于 `project.settings`；时长和时间方式属于项目，参考素材、边界及种子属于片段，不能因统一控件而改成同一作用域。

| 用户设置 | 持久字段 | 执行落实 |
|---|---|---|
| 单段核心 | `settings.recipe` | 选择 dance_split / 官方 / 兼容配方编译分支 |
| 底模 | `settings.model` | UNETLoader（节点 1）的 unet_name；当前文件原样提交，normalize 检查非空，不以文件名家族拒绝普通权重 |
| 一采面积与比例 | `megapixels / aspect / size_mode` | geometry 得到 32 像素对齐画布，传入视频条件节点 |
| 自定义宽高 | `width / height` | 真实条件画布；只在 custom 模式显示 |
| 二采倍率 | `scale` | MinimaxH3LatentUpscaler3D 节点 215 的 mode.scale；不是第二次面积 |
| 总步数 / 一采切点 | `steps / split_step` | dance_split：BasicScheduler 14 → SplitSigmas 289，二采使用剩余 sigmas |
| 采样器 / 调度器 | `sampler / scheduler` | 两采共享 KSamplerSelect 13 和 BasicScheduler 14；基线 Euler / beta |
| 二采独立降噪 | `refine_denoise` | 仅独立精修配方暴露；dance_split 不显示、不另建日程，整条 denoise=1.0 |
| 三 LoRA | `loras[{file,strength,bypass}]` | 仅启用且非零槽创建 LoraLoaderModelOnly；3 槽全 bypass 时加载节点为 0 |
| 官方加速 | `acceleration / accel_file / accel_strength` | 当前选择非空文件并按原文件加载节点 200；非零启用时按配方真实 8 步(T2VA)或 4 步(Ref2VA)，基础步数字段停用并说明；刷新列出文件不证明兼容性 |
| 低显存 | `low_vram / sage / head_chunks / ff_chunks / seq_threshold` | 真实注意力、前馈分块与 Sage 补丁；能力目录标注依赖是否安装 |
| VAE / 文本编码器 | `video_vae / audio_vae / clip` | 对应加载节点；保留完整文件名及当前选择 |
| 总时长 | `project.duration` | 每 ≤15 秒一个用户分镜；8/15/30/40 秒分别 1/1/2/3 段正文 |
| 单次上限 | `render_cap` | 内部渲染规划，不增加用户提示词数量；含上下文的 raw 不超过 15 秒 |
| 自然 / 精确时长 | `timing_mode` | 自然模式允许有效长度稍短；精确模式增加内部任务，不拉伸声画 |
| 连续 / 新场景 | `segment.boundary` | 继续时注入上一段上下文，新场景重置；换人场景边界由源视频切片确定 |
| 图片 / 音色参考 | `segment.asset_mode / assets / inherit_ids` | auto 空列表沿用 P01 并追加 inherit_ids；custom 只用本段列表及显式继承；none 不提交参考但保留原列表；旧缺字段按 auto |
| 随机 / 固定 | `segment.seed_mode / seed` | 每次生成决定 actual_seed，绑定 RandomNoise 12，运行记录显示实际值；0 有效，种子按十进制字符串校验 0～9007199254740991 整数 |
| 声音 | `audio_policy` | 默认 H3 声画；换人可选源音轨。参考声音仅约束音色及说话方式，不要求复制样本台词 |
| 帧率 | `export_fps` | H3 原生 24fps；导出重采样到用户选择帧率，保持时长和音速 |

## 官方文生与参考输入冲突

官方 T2VA 使用 FL2VA。加入图片或声音时，change-plan 给出改用官方 Ref2VA 的模型、加速文件和正文适配影响；取消保持原工作流，确认后 apply。预检只编译已确认的版本，不在生成时静默切换。此前文生预检的旧图片禁用判断已同步调整，避免界面允许上传但编译仍拒绝。

普通底模或加速 LoRA 文件当前不以家族名单／登记名单阻断。`model_families` 仍可作为内部能力描述，不是当前 `normalize` 的文件名许可表；实际文件兼容性由引擎执行反馈。已有工作流结构限制仍存在，例如官方配方只开放独立加速入口、文戏配方固定其双时钟步数和采样结构。阶段 B 保留这些视频行为及默认值。新增工作流与纯文件更新须分开处理。

## 跳舞核心边界

原 8＋4 编译连接保持不变。0.3MP / 9:16 实际一采 416×736，1.5×后按 32 对齐为 640×1088。节点 16 的中间去噪预测经过视频潜空间放大，与音频潜空间重组，节点 214 使用同一噪声、采样器、日程后半段完成二采。最终预览使用已选用交付结果；实际执行说明标识声画来源。长链扩展与生成质量、所有参数组合的显存占用仍不能由静态图检查证明。

## 图片任务映射

图片五工具 `single / dual / region / outpaint / text` 共用 `h3ui/image_studio/compiler.py` 的 settings、geometry 和 compile_graph；原四编辑分支从 `h3ui/image_studio/sources/krea-edit.json` 追踪真实输出，text按下述规则从单图链派生。字段属于 `image_tasks` 中当前任务，`service.py:plan` 归一化后由 change-plan／apply 保存，运行器固化 snapshot 与实际种子；不覆盖视频参数或历史运行。

精选公开字段来自 `h3ui/image_studio/parameters.py:public_parameters()`，通过 `catalog.parameters[tool]`（`parameter_contract_version=1`）提供稳定键、作用域、名称、分类、单位、范围及展开标记。`static/studio/features/image-settings/index.js` 据此生成右上唯一入口的分类弹窗；图片侧栏不再渲染快捷参数或第二个入口。画布工具“扩边设置”按同一描述读取四边精确值，与比例／锚点、拖动共同操作当前任务。旧 `quick` 描述及渲染帮助函数仍可存在，但不代表现行侧栏提供参数区。图片沿用公共分类顺序，按图片阶段显示“采样”“参考图”，不显示没有能力的低显存空组。

`core/image-catalog.js::assertImageCatalog` 检查真实目录 API 的版本和原四工具字段形状；声明文生图或当前任务为text时，额外要求text_to_image_version=1与parameters.text，图片路由进入、参数副本建立及目录刷新均复用该检查。旧网站进程返回缺失描述时显示前后端版本不一致，不显示空分类；目录刷新校验失败时保留此前目录和临时输入。这是网站接口契约检查，不校验生成组合或图像效果。

打开制作参数时克隆当前任务的 settings/models；取消、关闭或 Esc 丢弃临时编辑，保留打开前未保存的任务草稿。应用经校验后只更新当前任务草稿；后续“保存草稿”仍走原 change-plan／apply。应用、目录刷新均不重建画布或清空未保存笔画，不改提示词、素材、候选和资产。旧记录缺字段按适配默认读取，不迁移数据库或回写历史快照。恢复默认逐个遍历当前工具的公开字段：settings 从 catalog.defaults（compiler.DEFAULTS），models 从 catalog.models（compiler.MODELS 合并配置 image_models）读取；默认 seed=null 恢复每次随机，适用的四边扩图值也恢复。临时副本先验证默认值齐全，再整体修改；其他工具未公开字段保留。保存和编译继续使用本表原落点，无新增采样字段。快捷收藏的 select_output=false 是输出入库操作标志，不属于生成参数，不进入编译图。

| 用户设置 | 任务持久字段 | 执行落实 |
|---|---|---|
| 工具与编辑指令 | `submode / prompt` | 所选工具分支及提示词输入；单／双／局部／扩图使用各自输出节点，源节点连接由源图追踪 |
| 底模／图文编码器／VAE／编辑 LoRA | `models.unet / clip / vae / lora` | UNETLoader、CLIPLoader（type=krea2）、VAELoader、LoraLoaderModelOnly 原文件名；文生图仅前三种加载器，不加载编辑LoRA |
| 处理／输出像素面积（MP） | `settings.megapixels / output_mp` | 单／局部以 megapixels 缩放工作图并决定输出面积；双图及文生图以 ratio＋megapixels 得到最终尺寸；扩图固定 1 MP 工作图，output_mp 作用于扩边后的输出缩放。1 MP 按 1024×1024 像素计算，边长按 8 像素对齐；MP 是面积，不是画质承诺 |
| 双图/文生图输出比例 | `settings.ratio` | ResolutionSelector 使用同一几何规则算尺寸，实际写 EmptySD3LatentImage 宽高 |
| 四边扩展／羽化 | `settings.left / top / right / bottom / feathering` | ImagePadForOutpaint；四边像素基于 1 MP 工作图，拖动及精确输入使用同一任务设置 |
| 步数／CFG／采样器／调度器 | `settings.steps / cfg / sampler_name / scheduler` | KSampler 对应输入；当前选项及范围在 settings 中有现行限制，后续开放字段需核对真实节点来源 |
| 参考权重／图片 A 参考权重／参考适配方式 | `settings.ref_boost / ref_boost_a / fit_mode` | Krea2EditModelPatch 对应输入；ref_boost_a 仅双图公开并写入。其他工具保留任务中该隐藏值，但编译不消费，沿用其源分支原值。参考权重不等于保真百分比 |
| 图像理解尺寸 | `settings.grounding_px` | Krea2EditGroundedEncode 的 grounding_px，不是最终输出尺寸 |
| LoRA 强度 | `settings.strength_model` | LoraLoaderModelOnly 的 strength_model；当前四编辑分支一个编辑 LoRA 位置；文生图不消费该字段，没有另造独立 Bypass 参数 |
| 每次随机／固定种子 | `settings.seed` | 随机模式存 null，固定模式接受 0～9007199254740991 的十进制整数；固定 0 保留。前端保留非法输入并阻止应用，后端严格校验，不截断小数、不将非法值变随机。旧空字符串仍按随机读取。运行器确定本次实际整数并写 KSampler.seed，运行记录显示该次实际种子 |
| 图 A／图 B／局部遮罩 | `A / B / mask` | 项目输入 ID；执行时准备独立副本，原图与逻辑遮罩保留。局部语义标注不保证区域外像素不变 |

### 文生图派生适配

适配ID为image_assets/text，TEXT_ADAPTER_REVISION=1。原krea-edit.json只有四个编辑分组，没有现成文生图分组；文件保持不变，source_hash沿用其SHA256，plugin_version沿用86f886dac23013d88996e3a2e99093ba44d322fb来源记录。新增编译规则在内存中派生原单图输出27链，运行snapshot额外固定adapter_revision，实际提交图另存graph_hash；这些是来源/结构记录，不是已验证环境声明。

本地依据：<ComfyUI根目录>/custom_nodes/comfyui-krea2edit/__init__.py说明原生Krea2模型forward为文生图，编辑补丁另外拼接参考图条件，GroundedEncode在无图时转原生文本编码。本机启动脚本指向的ComfyUI源码目录为<ComfyUI根目录>；nodes.py的CLIPLoader支持type=krea2，CLIPTextEncode使用其原生tokenize/encode；comfy/text_encoders/krea2.py提供Krea文本模板和编码。只读取源码，没有运行脚本、插件或模型。

| 文生图实际输入 | 编译落点与固定行为 |
|---|---|
| prompt画面描述 | 节点36替换为CLIPTextEncode.text；负面节点34同类且保留空字符串；CLIP输入均沿用40，不加载参考图或编辑提示模板 |
| unet / clip / vae | 35以源UNETLoader43的完整widgets派生，直接接采样器；40 CLIPLoader保留krea2类型，41 VAELoader保持原链。默认文件仍从catalog.models读取，包含网站配置，不另造文生图文件默认 |
| megapixels / ratio | geometry与compile共用scale_size，MP按1024²像素、8px对齐，写节点28 EmptySD3LatentImage.width/height，batch_size=1；不从A获取尺寸 |
| steps / cfg / sampler_name / scheduler / seed | 仍写源KSampler30，保留原denoise=1、默认10步/CFG1/euler/simple；随机种子提交时固定，0有效，默认值来源不变 |
| 输出 | 源VAEDecode29→SaveImage27，保持原候选落库、校验尺寸、任务目录、入库与恢复；不是另一套提交器 |

text只公开上述字段；不公开或消费lora/strength_model、参考权重、图像理解、fit_mode、遮罩、扩边及output_mp。任务可保留未公开旧字段以兼容结构，运行snapshot的A/B/mask置空、inputs={}，不复制底图。所需节点通过编译图class_type求得missing_by_tool，执行模型校验只检查unet/clip/vae；原四编辑分支及默认图不变。跨文字/编辑工具在前端创建独立任务并保留原草稿，后续经原保存门持久化；所选文字结果继续编辑时按原规则创建single任务，以候选为A。不迁库，不重新设计图片工作区。

普通本地模型刷新走 `GET /api/v5/image-projects/catalog`，沿用 `LocalModels` 文件扫描；在线节点能力单独通过 `POST .../catalog/sync` 更新。图片底模／CLIP／VAE 使用与视频一致的 `select`，LoRA 使用可输入的 `datalist`；使用目录提供的完整相对文件名，目录未发现的当前选择保留并明确提示。远程引擎使用匹配该地址的节点缓存，不将本机扫描冒充远程模型目录；详见[模型目录](../local-model-catalog.md)。

接口与运行记录提供错误分类及 `error_raw` 原文，公共错误组件展示摘要、展开和复制原始反馈，原文中实际收到的节点／字段信息保留为文本，不猜原因或自动试参。后续字段变更同步本表与真实描述／编译，不复制到 AGENTS 或另一个能力全表。相关非生成检查与仍待生成、体验验证的范围统一见[维护基线](../maintenance-baseline.md)。


## V3 素材与提示词契约

`studio_inputs.inventory` 是标签顺序与节点连接的共同来源：先按有效素材顺序编号 Picture，再 Audio，换人再加入 Video 1。`studio_recipes.compile` 直接消费这些记录创建400起的加载节点和20的动态参考输入；不再另写一套编号算法。源视频用43连接20的 ref_videos.ref_video_0。输入清单记录媒体哈希、库固定版本、用途、加载/条件节点；公开页面不暴露内部 input_name。

- 当前草稿：POST input-preview，不保存项目，服务端解析项目内素材ID；未保存更改发生后旧响应不再显示。
- 已保存预检：GET preflight，用已保存修订构造图及 input_inventory。
- 实际提交：不可变运行清单保存真实图、输入和种子；不把最新预检冒充历史执行。
- 新项目 input_prompt_version=2；旧项目缺字段按1读。发声顺序字段 speaker_order，例如 `2,1` 对应 Subject 2=S1、Subject 1=S2；未指定顺序的新项目不以角色ID猜发声编号。旧模板保留兼容行为，并提示显式填写。
- V3 视觉接入时期曾使用 swap_prompt.version=2；现行能力目录的 swap_template_version=3，`studio_swap_prompts.py` 同时读取 1／2／3，并由 `swap_template_v3.py` 提供新模板。旧项目和完整自定义正文不自动覆盖；`features/swap-prompts/index.js` 提供显式升级。Picture 1 与 Video 1 区分目标图片和源表演，四视图拼图仍是一张图片。
- 换人声音参考与保留源原声冲突时，change-plan 列出改用模型声音的影响，确认后才应用。纯官方文生加入参考仍走已有工作流/底模联合确认。
- 资产 record_prompt/设定文案仅供档案，不进入 inventory、条件或生成正文。单图换人限制不扩展到其他支持多图的模式。

检查入口：test_director_v3.py、test_director_v3_routes.py、test_dance_split.py。测试编译真实图，不向真实引擎提交。
