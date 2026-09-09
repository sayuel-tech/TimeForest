# 检查与证据入口

2026-09-10 本轮运行：索引检查覆盖16个专题、7个模式、136个前端文件、18件图像资产；按专题与按文件查询已检查。现有体验接入与公共视觉尺寸检查通过，仍保留其历史 baseline 提示；这些均不是交互或用户认可验收。最终上下文结果以治理回执及现场 check 为准。

本次交付仅文档和定位工具；先执行索引默认检查、现有 context_guard。索引工具只判断可定位性与静态覆盖，不证明产品行为。

后续前端变化按既有要求运行 node tools/check_experience_contract.mjs；视觉相关运行 node tools/check_ui_design.mjs。它们的通过不等于用户认可，原五模式 baseline 不直接作为当前缺陷清单。

页面卡列出定向测试与 fixture。执行前阅读 fixture 的临时数据、假 API、真实隔离 API 边界；尤其图片可选 --real-image-api 不等于生产 API。全站项目图、媒体、数据库、密钥不用于写入验证。

维护工具的机械覆盖包括当前 static/studio 的 JS、顶层 styles CSS、static/index.html、styles tokens 和索引列出的字体 CSS；字体分片仅按清单计数，不逐个当成页面实现。动态导入/业务事件的全部可达性不在静态分析保证内。

八张已查看图片见 audit/evidence。网站交互、真实生成、性能与美术用户认可均未在本轮重验。文档/索引任务不需要重跑全部业务或启动生产服务。
