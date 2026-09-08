# 添加创作模式

本文件只处理真正新增用户任务的模式。先按需求选择入口，保留当前已认可的工作区和用户数据：

| 需求 | 维护入口 |
|---|---|
| 同用途的新工作流、已有工作流优化或替换 | [工作流适配契约](../governance/workflow-evolution-contract.md)，进入原功能选择器，输入和参数随所选工作流适配 |
| 开放已有工作流的一个字段、统一名称／单位／交互 | [参数映射](parameter-map.md)＋[统一参数与交互契约](parameter-and-interaction-contract.md)，复用原分类和控件 |
| 普通兼容模型或 LoRA 文件更新 | [本地模型目录](../local-model-catalog.md)，按现有加载器目录放文件、刷新、选择，不新增模式或维护认证名单 |
| 新的用户任务，现有功能流程确实无法承载 | 继续本文件的接入步骤 |

模型家族只是内部代码复用和适配依据，不决定产品一级模块。新增模式先定义用户任务及底层能力，再设计专属工作区；不能先添加生成入口，再研究实际编译能力。

## 共同体验先行

以上所有开发类别（包括不新增模式的字段、页面与工作流）都执行[体验准入](experience-admission.md)：先确定公共组件、作用域、业务差异和验收脚本。新增模式正式接入时同步登记experience-contract.json的modes，附真实检查记录；不能加入旧模式baseline豁免。结构检查通过之外，还须完成相同操作的交互、视觉与隔离保存/绑定检查。

## 接入步骤

1. 后端声明稳定 mode ID、允许配方及必需资产；补齐 `Studio.create` / 配方目录 / 预检校验。若需要新的输入节点，在编译器增加真实绑定及隔离图检查。
2. 创建 `static/studio/modes/<mode>/workspace.js`，导出 `navigation`、`className`、`renderEdit(ctx)` 和 `reviewComparison(ctx, segment)`。需要完全不同的制作页面时改用 `renderPage(ctx)`。
3. 在 `app/mode-registry.js` 注册 `{id, name, code, art, description, entry, load}`。首页与档案从注册表读元信息，不修改现有模式文件。
4. 从 ctx 组合素材、参数、提示词、预检、命令、导出能力。写字段后调用 `ctx.setDirty()`；规划变化调用 `ctx.schedulePreview()`；转制作调用 `ctx.switchTab('review')`。生成仅调用 `ctx.runAction`。
5. 新功能模块放在 features，接受项目 context，返回公开方法。不要访问另一模式内部实现，不直接 new 额外轮询。
6. 有监听器时通过 `mount(ctx)` 返回清理函数；需要结束处理时导出 `dispose(ctx)`。异步 UI 回调在 `ctx.session.disposed` 时退出。
7. CSS 放在模式类名下；在桌面、平板、手机核验布局。说明底层限制，并测试保存取消、失败、快速切换和旧响应返回。
8. 完成图编译检查和实际接入文档，再开放正式注册。不得用前端开关代替服务端能力实现。
9. 同批更新相关用法、唯一参数映射来源、工作流来源与必要 AGENTS 路由，校准[维护基线](../maintenance-baseline.md)后刷新上下文索引并检查。登记代码接入、非生成检查、真实生成和用户验收各自状态；不只改日期，不将文档维护延后到下一会话。未授权提交时，代码和文档保留在同一工作树。

## Context 常用接口

| 接口 | 职责 |
|---|---|
| `project / session` | 当前项目及会话；生命周期随路由 |
| `root / view / tab / shot` | 当前工作区 DOM、页签和分镜位置 |
| `catalog` | 服务端配方与参数能力 |
| `setDirty / schedulePreview / save` | 草稿变化、规划预览、确认保存 |
| `switchTab / renderProject / renderEdit` | 页签切换和视图刷新 |
| `commands / runAction / preflight` | 共享命令、错误反馈和编译检查 |
| `localAssets / bindAsset / uploadAssets` | 实际素材解析、绑定与上传 |
| `modal / confirm / toast` | 公共弹窗、确认及提示；关闭必须结束等待 |

## 历史扩展演练

仅在隔离服务新增 `tooling/mode-demo.js` 与 `mode-demo.html`，再由隔离服务暴露 `/checks/mode-demo`。注册 `acceptance_demo`，提供独立单页布局，复用真实参数模块，点击卸载后显示：会话已销毁、订阅 0、cleanup 1 次、dispose 1 次。未修改 swap、image-story 或 text-story 内部文件；未开放任何生成按钮。演示页不进入正式 static 目录。

此演练核验前端扩展和生命周期。全新生成类型仍须新增后端能力，不能据此宣称任意新类型可直接生成。

## 独立资产库接入

新增模式必须同时登记实际输入适配器、真实节点映射和输出入库来源，参见 [资产库与引擎适配结构](../asset-library-architecture.md)。复用库选择器与事务确认，不读取资产资料PROMPT作为制作正文。


## V3 模式设计交付清单

1. 写清该模式输入、主要编辑对象、声音/连续条件、每一步主要动作和失败恢复。
2. 用 workbench({rail, canvas, inspector, kind}) 组合专属主画面；文生不必放大块图片空位，视频编辑应优先留画面空间。需要全宽导出或双栏源准备时明确独立 kind。
3. 属性可复用 propertyTabs；绑定调用 bindWorkbench。分镜编辑复用 bindEditors，不复制保存代码。页面不再调用 append 创建无上下文操作按钮。
4. 新输入类型先修改 studio_inputs.inventory/validate 与编译器消费路径，再修改模板和 UI 清单。Picture/Audio/Video 来自有效输入序列，Subject/S 来自语义和发声顺序，不能互相推导。
5. 空、忙、失败、满数据四种状态先在隔离服务走查。最少核验1280×720主动作可见、窄屏字段可达、长目录不撑高页面、保存取消不提交。
6. 实际发布时同步唯一 static/index.html 静态入口版本和能力契约；文档维护不据此发布或改入口版本。记录旧项目缺字段默认值，不批量改写旧正文或运行候选。

新增模式须调用[完整公共界面入口](shared-ui.md)，不自行创建参数容器或复制外壳CSS。检查公共样式实际生效与全部调用模式，而不是只检查导入了公共函数。6.3.13已修正拼接参数/底栏分叉并接入参考素材，业务会话仍独立。

## 视频序列接入实例

已接入video_assembly，kind=assembly，由bootstrap分派独立序列控制器。此任务的原片/续写结构与故事分镜不同，因此复用公共呈现、API边界和watchProject，而不是强行投影到ProjectSession的segments。后端输入、保存、编译、运行、入库与恢复均有对应适配，目录与health显式返回assembly_contract_version=1；旧后台不展示入口。最初计划和现行差异见[视频拼接说明](../video-assembly.md)。
