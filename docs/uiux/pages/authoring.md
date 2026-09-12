# 剧本创作

**v6.3.35 功能状态：剧本创作模式和电影创作模式目前不可用。** 本版保留开发中的页面与代码，尚未完成可用性与完整创作流程验收；请勿将这两个模式视为已交付功能。后续状态以版本说明为准。

维护 ID：`authoring`。关键词：剧本、资产落实、资产绑定、分镜、片段Prompt、沟通、完整资产剧本。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>?step=0..4`：故事起点、剧本创作、资产落实、分镜设计、片段 Prompt。数字是零基步骤。对象定位还须读 shot-segment-tree/return-context。

## 保留优先

保留五页、跨页目录、对象隔离沟通和同一输出确认、全剧/分镜/片段真实资产作用域。用户要求第三页保留左目录、上资产下剧本。

## 修改边界及联动

现有资产需求已接入具名媒体网格、类别/待落实筛选和主操作/更多配置，资产区旧固定内滚动已移除；这些旧问题不再作为未实施任务。当前卡片密度已按后续反馈调整，最终业务可读性与整体体验仍待用户确认。后续按具体反馈维护 binding-cards.js 与 creation.css，不重写后端绑定解析；h3ui/creation/bindings.py 仍是有效资产解释入口。具体实现及历史问题见 site-experience 与 audit/findings。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/features/authoring-assist/binding-cards.js](../../../static/studio/features/authoring-assist/binding-cards.js) | `resolveBindings`, `mountBindingCards` |
| [static/studio/features/authoring-assist/conversation.js](../../../static/studio/features/authoring-assist/conversation.js) | `writingScope`, `conversationKey`, `scopedJobs` |
| [static/studio/features/authoring-assist/create-project.js](../../../static/studio/features/authoring-assist/create-project.js) | `createCreationProject` |
| [static/studio/features/authoring-assist/image-handoffs.js](../../../static/studio/features/authoring-assist/image-handoffs.js) | `mountImageHandoffs` |
| [static/studio/features/authoring-assist/index.js](../../../static/studio/features/authoring-assist/index.js) | `updateAssistStatus`, `mountAssist`, `bodyText` |
| [static/studio/features/authoring-assist/output-editor.js](../../../static/studio/features/authoring-assist/output-editor.js) | `structuredOutput`, `bindStructuredOutput` |
| [static/studio/features/authoring-assist/prompt-fields.js](../../../static/studio/features/authoring-assist/prompt-fields.js) | `promptFields`, `profileMarkup`, `promptMarkup`, `bindAuthoringPromptTools` |
| [static/studio/features/authoring-assist/references.js](../../../static/studio/features/authoring-assist/references.js) | `mountReferences` |
| [static/studio/features/shot-segment-tree/edit-preview.js](../../../static/studio/features/shot-segment-tree/edit-preview.js) | `previewEdit` |
| [static/studio/features/shot-segment-tree/index.js](../../../static/studio/features/shot-segment-tree/index.js) | `shotSegmentTree` |
| [static/studio/features/shot-segment-tree/return-context.js](../../../static/studio/features/shot-segment-tree/return-context.js) | `readReturnContext`, `returnHref`, `withReturnContext` |
| [static/studio/modes/authoring/workspace.js](../../../static/studio/modes/authoring/workspace.js) | `mountWorkspace` |
| [static/studio/styles/creation.css](../../../static/studio/styles/creation.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/authoring.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

具名缺口可识别；无需求不能伪造卡片；编辑/确认保留身份；全剧覆盖来源准确；图片补充后返回正确对象。

- [tests/creation_return_context.test.mjs](../../../tests/creation_return_context.test.mjs)
- [tests/creation_experience_ui_fixture.py](../../../tests/creation_experience_ui_fixture.py)
- [tests/test_creation_experience.py](../../../tests/test_creation_experience.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/creation-experience-implementation.md](../../frontend/creation-experience-implementation.md)
- [docs/product/creation-experience-correction.md](../../product/creation-experience-correction.md)
- [docs/creation-modes.md](../../creation-modes.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

资产需求已改为具名媒体网格及主／次操作；筛选按对象保留而不保存项目。上资产下完整资产剧本；五页目录和真实绑定、局部覆盖、同一输出编辑保留。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。


本轮信息密度、字体与动效更新（2026-09-10）见[修复记录](../../frontend/density-font-motion.md)。原版字体实际加载、标题字重与减少动态效果分别核对；原素材／媒体／正文和保存语义保留。

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 把想法发展为资产明确、分镜/片段明确、可供制作的剧本。
- **第一眼最想看见什么？** 起点看输入；写作看沟通与输出；资产页看具名缺口；分镜/片段页看当前对象。
- **最自然的动作：** 故事/图片 → 沟通确认完整剧本 → 分析并绑定资产/整理资产剧本 → 分镜及片段 → 完成Prompt
- **空间判断：** 五页有不同空间任务。2/4/5上沟通下输出、右侧当前参考/有效资产；3保留左目录，上资产下剧本，无右栏。目录跨页导航。
- **必须保留：** 无段落业务层；全剧→分镜→片段继承及单项覆盖；固定版本、对象隔离沟通、候选原文、原保存冲突门。
- **直接验收场景：** 网格已接入，不再从零重做；待核对8项混合需求、未绑定/已绑定/文字/停用、详细关系可发现性与正文可读性。真实LLM质量不在隔离检查结论中。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。

## Q1：具名资产位置与阅读（2026-09-10）

本次核对发现缩略区64px、名称13px不利于辨认，未绑定图位不能直接操作。现将图位本身作为“为某个名称绑定素材”的按钮；已绑定图位仍可预览，下方提供更换。复用原资产选择器及保存/固定版本链，不新增绑定协议。文字设定、未使用和待落实分别显示；服装/声音保留关联角色，来源与详细配置仍可查看。

卡片沿用首页纸面、柔和边界及标题字重，预览112px、名称16px，宽屏按可用空间排网格，窄屏保留可操作图位。此尺寸属于绑定任务，不全局放大其他资产卡。八项需求会令下方剧本超出首屏；主区统一滚动，正文仍占主区宽度，不把资产固定成小滚动窗，也不压缩正文来满足旧三项需求的首屏行数。保留左侧跨页目录及底部保存/确认。

隔离入口：`tests/creation_experience_ui_fixture.py --q1 --r1 --page 2`，临时项目/库、合成图片及fake写作末端。1366×768与430×900场景涵盖8项混合需求、分类重绘保持、首次选择取消、更换取消、实际选择固定版本、保存后重挂载、资产剧本确认及分镜/片段来源。滚到剧本后分别可读8/10行，首屏为0行，二者明确区分。公共卡片另检查片段侧栏；15项公共规范/准入检查通过。

证据目录：`<本地维护路径>`（wide、narrow、clip-inspector的page.png/page.html/checks.json）。截图中的色块为隔离素材，只验证区域与操作，不代表真实人物辨认质量。未读取生产项目或密钥，未真实生成、重载或发布；用户视觉体验及剧本/电影整体可用性仍未验收。当前进度及下一批只见维护基线。

## Q2a：完整剧本沟通与输出（2026-09-10）

实际差异：沟通输入44px且被按钮挤窄；输出状态被替换进aria-label，画面只剩“当前输出”；版本按钮嵌在summary里混合选择与折叠。现在由原experience-content适配移动原节点，版本/比较独立于折叠，状态直接可见。2/4/5页共用全宽多行沟通，文字用阅读字号；第3页保留资产整理的业务适配。未新建模式私有对话组件或改写事件链。

第二页把原故事起点移入“故事起点与创作依据”，可展开全文，避免辅助摘要常驻挤压正在编辑的完整剧本。右侧参考、底部保存/确认与下一步、原纸面与字体保留。版本较多可横向查看，不无限堆叠压缩正文。无候选时说明输出会出现的位置与确认步骤。

片段联查发现共同writing-surface原固定最小高度不足以容纳展开后的沟通与输出，会使下方工作流关系重叠；改为按内容确定最小高度，空间不足时由工作区滚动。增加输出与片段设置不重叠的宽窄断言。分镜/片段自身的阅读布局继续在Q2b核对，不把此次共同容器修复当作该批完成。

`creation_experience_ui_fixture.py --q2 --r1 --page 1`：临时真实保存/确认接口，fake写作末端，12段合成长文；桌面1366×768及窄屏430×900通过。主动注入503保存失败，验证正文/沟通保留且任务数量不增加，随后重试保存确认；迟到快照不换掉正在编辑的节点；版本返回还原已保存编辑稿，历史候选原文保持。另完整走过原五页及片段共用呈现，未调用真实LLM或生产数据。15项公共规范/准入通过。证据 `<本地维护路径>`。这些检查不能替代真实创作体验或Q2b的对象/资产关系验收。

## Q2b：对象定位与资产继承（2026-09-10）

已存在的跨页目录、按对象隔离的沟通和真实继承解析保留。本批补上主区/资产区同一分镜名称及片段序号，基础来源选择显示所属分镜名称；单项覆盖数量显式可见，规则折叠说明，避免全部解释占据侧栏。每张卡仍按实际解析结果显示来源，不把基础选择框的值冒充所有卡片来源。

普通点击资产来源经ctx.navigateWriting复用原leave/save门，取消留在当前对象，保存后定位来源页；进入片段展开其所属分镜。Ctrl/新窗口链接行为保留。基础来源变化不清理已有单项覆盖，恢复沿用使用原“更多→素材来源”。本批未改后端bindings.py、工作流、固定资产版本或Prompt任务语义。

隔离入口：`creation_experience_ui_fixture.py --q2b --r1 --page 4`。1366×768与430×900分别检查分镜文字设定→片段沿用、片段直接全剧绑定、单项停用在切基础时保留、恢复沿用、来源跳转留在此页/保存后跳转、返回读取片段自己的沟通；窄屏侧栏有实际开合断言，最终截图侧栏关闭不代表素材未挂载。3项test_creation_experience检查覆盖后端实际继承、写作输入与电影固定引用及局部确认，17项Node检查通过。证据 `<本地维护路径>`，全程临时数据/fake末端，无真实模型或生产重载。最终用户体验及电影流程仍按维护基线状态。


## 手工正文换行保护（2026-09-12）

后续业务修复，不重开Q0—Q7。真实临时API保存故事起点的原文正确，但保存后重绘textarea会由HTML解析吞掉第一个换行；用户继续编辑可能把变化写回。authoring/workspace的通用文本框和authoring-assist的沟通/候选正文模板补一个浏览器消耗的前导换行，与原三视频正文做法一致；不trim、不改后端文本或内容身份。

新增 [手工剧本检查](../../../tests/authoring_manual_text_ui_fixture.py)。修复前1366×768、430×900均在“API原文正确/重绘缺首个换行”处失败，修复后两档通过故事起点保存、手工粘贴完整剧本、沟通保存、重开原文、继续编辑、内容ref不变及完整剧本确认；模型任务与候选均为零。宽窄截图实际查看，保留原布局与正常段落滚动。证据 `<本地维护路径>`，red/green分开保留。浏览器采集使用独立子进程，保持业务夹具禁止外网连接；未改网络保护。

这只关闭文本完整性缺陷，未证明剧本到电影的完整业务可用。后续具体缺口应沿原纠偏流程逐项复现，两个模式的不可用声明保留。

原creation_experience_ui_fixture在1366×768以fake LLM末端通过五页链路（9次替身响应），含基于上次输出继续、候选编辑/确认、保存失败与迟到响应保护；本轮未改此夹具。真实LLM仍未调用。


## 用户自定义云端接口（2026-09-12）

制作参数沿用公共外壳，新增DeepSeek/兼容Chat Completions选择及JSON返回方式；地址、模型、密钥、视觉与输出token保持用户可编辑。取消不保存，应用留草稿，保存才作用于新请求。旧配置不自动改模型，密钥留空保留；字段说明明确全剧本作用域。无custom_chat_version=1的旧后台提示重启。

[后端契约检查](../../../tests/test_authoring_custom_provider.py)验证新模型/地址/token/response_format进入替身请求，后续换模不改旧任务快照、密钥不回显、原DeepSeek/未接入本地类型保护；连同原DeepSeek候选应用共3项通过。[设置夹具](../../../tests/authoring_provider_settings_ui_fixture.py)使用真实临时API，两档通过取消、应用、项目保存、弹窗直接保存及重开；1366×768/430×900截图已查看，沿用纸色和公共参数布局，窄屏正常滚动。证据<本地维护路径>；ui为内嵌契约未同步的失败，ui-final为夹具错误等待关闭节点消失，均已修正。无真实账户请求或生产重载，部署后须新后台加载；模型服务兼容性由实际协议决定，两个创作模式整体不可用声明未解除。
