# 换人通用模板 v3：依据、实现与使用

核对日期：2026-09-06。官方main提交d21241f0a4b3acbb34c97dae47fa417b7065e438。此版本用于时间森林的单张角色图＋一个源视频整体换人，不是模型官方发布的现成万能模板。

## 研究来源与证据等级

1. [H3官方提示词技能](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/SKILL.md)及[全参考规范](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/references/ref-en.txt)：六段结构、英文描述、引用与声音关系；人物与源视频分别定义，外观/动作具体说明。作为格式权威。
2. [RecycledSpoons的V2V换人模板](https://www.reddit.com/r/StableDiffusion/comments/1vjf2v9/minimax_h3_characterobject_v2v_swapping_template/)：作者报告可用，强调简短但具体的目标外观与源动作描述。采用其“点名替换对象及可见属性”的经验，不照抄可选Picture 2等占位内容。
3. [Testing Character Swap with MiniMax H3](https://www.reddit.com/r/comfyui/comments/1vinc36/testing_character_swap_with_minimax_h3/)：作者展示结果；评论同时指出过长模板和输入编号问题。采用“来源职责与真实输入一致”，不把某一长模板当普适定律。
4. [原人物保留问题及F_DeePee的实测回复](https://www.reddit.com/r/StableDiffusion/comments/1vitypf/minimax_h3_r2v_character_swap_keeps_original/)：强调人物服装描述与人物执行动作，减少重复引用源视频。采用这一方向，但不照搬其未对应本工作台实际条件的Audio标签。
5. [双人换人的自述经验](https://www.reddit.com/r/StableDiffusion/comments/1vojyye/minimax_h3_ref2v_character_replacement_prompting/)：说明目标对应关系与具体外观有用，也显示额外Subject并不等于额外图片。它含自定义保留枚举，不按官方枚举照搬，也不把双人经验当单图质量保证。

社区“成功率”属于作者自述，未在用户配置复现实测。官方格式、本站节点绑定、生成画质是三种不同证据。

## 修订了什么

- v2固定声称参考图有多个视图；v3仅条件性处理多视图，不臆测未识别的新图片。
- 将具体目标外观加入subject_definitions及人物出场描述；将源人物与动作说明放在detailed_description。两者分别使用现有片段字段staging、beats，不读取资产record_prompt。
- 用目标人物执行源表演的正向描述组织正文，减少“逐帧完全保留源视频”的重复要求；人物的体型和服装决定新轮廓，而表演位置与节奏来自源片，不要求保留原身体外形。
- 目标人物Subject采用实际角色ID；单张图片仍只有Picture 1。源Video 1只对应真正接入的切片。未接入声音不产生Audio标签。
- H3生成声音时，声线说明、参考声音、环境声及配乐分别写入正文对应部分。保留原声时模型声音段为N/A，由既有后期音轨装配处理，不能虚称原声作为Audio参考已送入模型。
- 有声音参考但角色ID不匹配时明确拒绝，避免引入未定义的新人物。多发声主体仍用完整自定义正文。
- 保留旧v1/v2以及完整自定义的逐字内容。新项目与“从通用模板复制”用v3；旧项目通过显式升级进入v3，不改历史候选。

## 页面使用

1. 源视频与角色 → 提示词 → 升级通用模板至v3；若项目采用完整自定义，升级版本本身不会替换其正文。
2. 分段与替换 → 本段提示词方式选择“通用换人提示词”。
3. 按需展开“具体角色与原表演描述”。推荐英文；没有内容也能使用通用模板，但它不会自动识别素材。
4. “目标外观”写实际角色图中的发型、服装颜色/剪裁等。“原人物与本段表演”写替换哪个原人物、动作和镜头变化。不要将原人物服装写成目标服装。
5. 查看最终提示词在原编辑区下方展开。想完整编辑：从通用模板复制并编辑本段；此后只提交自定义正文，不额外拼接隐藏模板。

用户之前提供的灰裙角色图，可参考以下目标外观描述（只作为该图的例子，不是所有项目默认值）：

> a woman with long brown hair, wearing a fitted gray off-shoulder button-front knit minidress and pale strappy high-heeled sandals

源表演描述必须针对实际片段，不能把其他案例的走路、烹饪或镜头轨迹填进当前视频。源片段包含硬切时，按实际切点在完整自定义正文内写后续Shot和时间；当前通用模板不会自动猜测切点。自动切片仍使用原服务。

## 实现与验收

- h3ui/swap_template_v3.py：结构化模板；studio_swap_prompts保留版本路由；两条换人核心使用同一提示词生成入口。
- preview、复制模板、保存编排和真实编译都接收staging/beats；实际图条件节点20的prompt经检查与构造结果一致。
- 7项新模板检查、7项旧兼容检查、4项路由检查通过，无引擎提交。
- 隔离浏览器完成旧模板升级确认、两项描述填写、下方最终提示词核对；六段各出现一次，新描述进入正文，没有预检弹窗。
- 配方、两采、显存模块、源切片与合成算法不改动。不能由这些检查证明已经解决人物身份或服装的生成效果。
