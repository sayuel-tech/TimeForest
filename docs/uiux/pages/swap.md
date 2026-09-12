# 参考视频换人

维护 ID：`swap`。关键词：换人、源视频、目标角色、对照审核。

[返回总索引](../README.md) · [盘点与证据等级](../audit/inventory.md)

## 页面与责任

`#/p/<id>`，mode=swap。步骤键 source → edit → review → export，页面为源视频与角色、分段与替换、对照审核、成片。

## 保留优先

保留源表演/目标角色的明确区分、原片与结果对照、片段审核及成片入口；共享工作区位置是已有基础。

## 修改边界及联动

工作区由 app/workspace-controller.js 组装。分段准备、替换提示词预览和最终审核有不同职责；布局调整不能改变切段、接受候选或自动推进语义。

## 源码入口（2026-09-10 核对）

| 路径 | 可搜索符号（节选） |
|---|---|
| [static/studio/features/source-preparation/index.js](../../../static/studio/features/source-preparation/index.js) | `createFeature` |
| [static/studio/features/swap-prompts/index.js](../../../static/studio/features/swap-prompts/index.js) | `createFeature` |
| [static/studio/features/swap-prompts/preview.js](../../../static/studio/features/swap-prompts/preview.js) | `createPromptPreview` |
| [static/studio/modes/swap/workspace.js](../../../static/studio/modes/swap/workspace.js) | `navigation`, `className`, `renderEdit`, `reviewComparison` |
| [static/studio/styles/modes.css](../../../static/studio/styles/modes.css) | 文件入口 / 样式定义 |
| [static/studio/styles/task-layouts.css](../../../static/studio/styles/task-layouts.css) | 文件入口 / 样式定义 |
| [static/studio/styles/workbench.css](../../../static/studio/styles/workbench.css) | 文件入口 / 样式定义 |

符号与路径用于定位，不以固定行号作长期依据。更细的静态导入/反向调用和指纹见 [机器定位图](../maps/swap.json)；动态字符串和业务调用须继续核对源码。广泛改动还要读 [跨页流程](../workflows/README.md)。

## 本任务相关检查

来源与结果是否易区分；取消保存不开始制作；末段审核进入成片；参考与主画面都可读。

- [tests/studio_source_preparation.test.mjs](../../../tests/studio_source_preparation.test.mjs)
- [tests/studio_frontend.test.mjs](../../../tests/studio_frontend.test.mjs)
- [tests/result_experience_ui_fixture.py](../../../tests/result_experience_ui_fixture.py)

以上仅列可选定位入口，不表示本轮运行这些业务检查；按实际改动筛选并先确认临时数据边界。

## 详细规则

- [docs/frontend/README.md](../../frontend/README.md)
- [docs/prompts/swap-template-v3.md](../../prompts/swap-template-v3.md)

维护此页时同时更新 catalog 对应条目、刷新机器图并执行链接检查；具体步骤见 [更新约定](../maintenance.md)。

## R1布局接入（2026-09-10）

原片与结果对照保留，候选记录移至对照主区下方；实际运行记录、选用影响确认、入库和移除复用原事件。 布局以用户提供预览为目标，美术沿用原站。源码归属、检查与局限见[本次接入](../site-experience.md)。

## 任务导向设计目标（2026-09-10）

本节是后续逐批核对的目标，不表示现有界面全部符合，也不覆盖已明确保留的原版首页/顶部导航。执行状态只见维护基线，批次见[实施计划](../task-led-plan.md)。

- **用户为什么点进来？** 保留源视频表演，让指定角色进入画面。
- **第一眼最想看见什么？** 源片与目标角色是否准备好；审核阶段优先看到源片/结果对照。
- **最自然的动作：** 选视频与角色 → 确定范围与替换要求 → 生成 → 对照选用/重做 → 合成导出
- **空间判断：** 准备页围绕源片和角色；审核页给对照媒体主要空间，进度与参数辅助；不能把正文或状态框挤成主体。
- **必须保留：** 原执行分段、审核/自动推进、原声音规则、固定候选和采样。
- **直接验收场景：** 准备、运行、候选、成片分别核对；共用审核组件改动联查参考图/文生两模式。

改动前用当前源码与对应隔离场景区分“已满足/真实差异/待确认”，只修改真实差异；未复核项不能写成已发现缺陷。气质、行为、组件统一，不要求空间结构相同。

## Q4a：准备与对照审核（2026-09-10）

核对当前宽窄画面后保留原片/结果并排对照、窄屏纵向对照、角色侧栏及原候选行为。准备页原角色图片没有可见名称，窄侧栏两项导入挤成多行；现在源视频标题下显示文件名，角色用具名figure保留原固定版本链接，侧栏本地/资产库导入上下排列。原上传、准备、切片与审核自动推进逻辑未修改，美术及公共播放器未替换。样式仅限定source-desk，未改其他两视频模式。

`tests/swap_layout_ui_fixture.py`使用真实前端及受控API/合成视频，1366×768与430×900覆盖准备/审核四场景；检查媒体载入、两侧对照、素材名称、窄屏侧栏打开及导入宽度，无横向溢出、零生成请求。初始夹具缺少提示词收录接口和媒体路由导致的提示已修正，不能当成生产缺陷。`studio_source_preparation.test.mjs`四项通过，覆盖先保存后准备/取消/陈旧切片保护/进度局部更新；结果夹具swap两档通过播放定位重试、入库不选用、移除恢复及选用/重做取消。浏览器API受控而非生产后端，不证明真实上传准备或模型质量。证据 `<本地维护路径>`；before/after是本轮源码截图，results为原结果行为复核。最终视觉仍待用户反馈。
