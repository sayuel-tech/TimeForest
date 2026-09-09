# 任务与可阅读性 V2 检查证据

2026-09-09。对应[本期实际交付](../../frontend/readability-implementation.md)。[截图浏览](gallery.html)收录本轮代表页面，均为临时内容和已有网站美术，不含生产项目。

| 检查 | 结果文件 | 本轮范围 |
|---|---|---|
| 页面覆盖清点 | workspace-inventory.json | 44个模式/步骤/宽度或参数场景；含七模式23步骤。检查入口、区域与响应式，不单独代表可阅读性。 |
| 七模式长正文 | long-workspaces.json | 14个宽窄场景：正文17px、结束可达；属性开关保留原编辑器节点与输入；电影读取已持久来源正文。剧本约1500字，其他提示词600字以上。后续6项重点复查覆盖原场景，不重复计数。 |
| 查找/全文/资料 | reading.json | 10个宽窄场景：四篇不同摘要，读到末尾约束，上一/下一条，返回保留DOM/筛选/滚动/焦点，选出确切完整文字；资产预览不选择，展开资料取消不改字、应用只改本机草稿。 |
| 管理页面 | management.json | 首页、档案、资产任务、存储、分类、回收站、详情、全局任务，共16个宽窄场景；合格区域保留。 |
| 结果/媒体 | results.json | 五模式10个宽窄场景：查看与选用区分、入库不切步骤、不改选用，移除/恢复，合成媒体播放/暂停/拖动/错误重试。审核高度修正后的同场景复查覆盖旧结果，不重复计数。 |
| 重绘保护 | refresh.json | 七模式：相同轮询不重绘、状态局部更新、内容变化保留展开、输入草稿保护、按身份重排状态节点。 |
| 参数交互 | parameters.json | 原三视频与图片12项：模型手动输入/分组、取消与重开、宽窄底部操作可达；另有七模式参数覆盖和剧本/电影取消检查。 |
| 保存与收录 | prompt-save.json | 两种宽度下五模式实际临时API保存、收录、固定版本、字段组合和取消。 |
| 剧本/电影流程 | creation-flow.json | 两个真实页面→临时API→持久化场景；剧本保存/取消，电影fake生成末端/选用/剪辑/返回来源。只调用测试替身。 |

另运行 `node tools/check_ui_design.mjs`、`node tools/check_experience_contract.mjs` 及 `node --test tests/ui_design.test.mjs tests/experience_contract.test.mjs tests/studio_task_center.test.mjs`，18项Node用例通过。全部114个前端JS文件语法检查通过，见 `syntax.json`。两个准入工具只检查归属/结构；历史五模式总体登记保留，不据此宣称完整体验认证。

可复现入口为 `tests/readability_ui_fixture.py`、`tests/site_layout_ui_fixture.py`（`--readability`、`--modes`可限定）、`tests/library_layout_ui_fixture.py --general` 及对应原有fixture。所有环境使用临时目录、临时Flask配置、已有Python/Chrome；creation保持外连禁止。原三视频结果fixture的部分外围API为受控替身，所以它只证明界面与操作结果，不能证明真实生成。

检查中出现过两次Chrome在Windows创建DevToolsActivePort后的短暂占用；捕获器原先只检查存在，现改为限时等到可读。受影响场景重新执行通过，未降低网站断言。第一次长文本样例不足600字，已补充独立参考约束后重做阅读检查；不把短样例计为长文验收。

原始截图/DOM/临时浏览器配置保留在本机检查目录；这里只收录去重后的检查结果和代表截图。V1证据保留为历史，不能替代本批。

没有生产重载、生产密钥读取、真实LLM/视觉/ComfyUI调用、模型加载、真实作品生成或自动发布。没有大型资产库、大文件断网续传或长时间多窗口测试。用户实际审美和真实生成反馈不作为无限扩测的前置门槛。
