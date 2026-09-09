# 跨页维护：按完整动作定位

| 用户动作 | 先读 | 继续追踪的代码（仓库根相对路径） | 必须保留 |
|---|---|---|---|
| 项目继续/离开 | [首页](../pages/home-projects.md)、[状态](../common/state-feedback.md) | bootstrap → confirmLeave → 对应 saveBeforeLeave | dirty/working 与返回位置 |
| 剧本补图后返回 | [剧本](../pages/authoring.md)、[图片](../pages/image-assets.md) | authoring-assist/image-handoffs.js → 图片控制器/transfer；h3ui/creation/handoffs.py | 来源目标、草稿、旧关联 |
| 剧本到电影再返回 | [剧本](../pages/authoring.md)、[电影](../pages/movie.md) | shot-segment-tree/return-context.js → 两个 workspace；creation/service.py | 固定身份、父分镜、原电影位置 |
| 选素材到实际使用 | [资产](../pages/asset-library.md) | asset-picker/project-use/destinations/assembly-use → 项目保存 → h3ui/asset_library/usage.py | 选择不冒充已使用、固定版本 |
| 生成到选用/入库 | [视频结果](../common/production.md)、对应模式 | result-view → candidate-records / result-import / image-results/transfer | 选用与入库独立，保留候选历史 |
| 查找Prompt到运行记录 | [提示词](../pages/prompt-library.md) | browser → adapters → 保存 → collection/records；h3ui/prompt_library | 草稿、固定内容、收录失败回执 |
| 轨道到成片 | [接续](../pages/video-assembly.md)、电影 | track/workspace → h3ui/video_assembly/track.py 或 h3ui/creation/movie.py | 屏幕顺序与实际导出对应 |
| 任务异常与恢复 | [管理](../pages/management.md) | task-center → h3ui/task_center.py；recycle-bin → studio_recycle.py | 精确停止、真实状态、可恢复标记 |

表内缩写用于检索；模块是否存在由索引检查与源码共同核对。生成核心或持久化规则不因 UI 调整而自动修改。跨页场景的测试入口随页面卡列出，只有受影响的路径需要执行。
