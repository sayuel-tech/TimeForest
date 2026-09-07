# 分类回收站

资产库侧栏“回收站”是统一查看和恢复入口，内部固定三类：

| 分类 | 收录内容 | 恢复位置 |
|---|---|---|
| 资产库移除的 | 资产库已有 deleted 标记的资产，保留缩略图和查看资产入口 | 原资产列表；支持本页选择与批量恢复 |
| 项目移除的 | 图片、三个视频模式及旧版 Registry 中带 deleted_at 的项目，以及带 discarded_at 的图片编辑任务 | 项目回原项目档案，编辑任务回所属图片项目；原有“已删除”筛选仍可恢复 |
| 生成移除的 | 图片 run 与三个视频模式 attempt 中带 removed_at 的记录，包括失败/取消且没有输出的记录 | 所属任务的候选或运行记录；不自动选用或生成 |

三个分类各显示数量，可搜索名称、任务、记录编号或种子，每页24条。搜索只作用于当前分类，切换分类清除搜索与页码，不继承资产库其他筛选。旧 `#/assets?trash=1` 入口兼容到第一类；规范入口是 `#/assets?view=trash&recycle=assets|projects|generations`。原项目内“已移除”区保留，并提供统一回收站链接。

所属项目已被移除时，生成记录仍可在回收站中看见，但须先去“项目移除的”恢复项目。图片编辑任务废弃后在“项目移除的”中恢复；显示任务名称及所属项目，父项目已删除则先恢复项目。任务恢复不自动选用或生成，仍被单独移除的候选继续留在“生成移除的”；恢复候选前也须先恢复其编辑任务。恢复项目不自动恢复其中已废弃任务或另行移除的候选；恢复候选也不改变原选用结果、资产版本或固定引用。项目仍有执行/待确认提交或版本已变化时，沿用原操作拒绝规则，显示真实错误；列表中的提示不能替代后端校验。

此回收站不提供清空、永久删除或文件清理，不会释放磁盘空间；原视频独立“磁盘清理”仍有自己的文件边界，恢复可见性不能重建用户另行删除的文件。已存在的移除标记直接可见，无需迁移或重新移除。

## 实现

`h3ui/studio_recycle.py` 提供只读 `GET /api/v5/recycle-bin?category=assets|projects|generations&page=1&q=`。从现有 LibraryStore、StudioStore、ImageStore 和 Registry 汇总；返回三个总数量及当前类分页项，不写新表或另一份回收站状态。图片预览只在所属项目未删除时提供，分页资产预览沿原公共媒体URL。

`static/studio/pages/asset-library/recycle-bin.js` 复用资产库壳层、原确认对话框、API错误组件和公共工作区视觉变量。分类使用可直接打开的链接；请求跟随原路由 AbortSignal，离开后不回写旧页面，不重试恢复请求。恢复请求由记录类型映射到原接口，保留原revision与归属：

- 资产：`POST /api/v5/library/assets/<id>/trash`，`restore:true`。
- 现行项目：`POST /api/v5/projects/<id>/trash`，`restore:true`。
- 图片编辑任务：`POST /api/v5/image-projects/<pid>/tasks/<tid>/discard`，`restore:true`及项目revision。
- 旧项目：`POST /api/v5/legacy/<id>/trash`，`restore:true`。
- 生成：`POST /api/v5/projects/<pid>/records/visibility`，`removed:false`，视频附稳定segment ID。

资产批量恢复逐条使用其原revision；中途失败报告已完成数量，不自动重试或回滚其他已成功恢复的资产。项目/生成记录逐条恢复，避免同一项目连续操作拿旧revision覆盖修改。

## 检查

`tests/test_image_task_discard.py` 核对编辑任务废弃/恢复、父项目和单独移除候选分离、旧草稿/直达接口不能复活及空任务项目重新保存。

`tests/test_recycle_bin.py` 使用真实Flask工厂、临时数据和假引擎，验证只读分类/分页/搜索、三视频与图片及旧项目、父项目删除、恢复保留文件/快照、版本/待确认保护。真实API JSON交给实际JS生成恢复请求，再调用真实原接口；不是模拟恢复契约。

`tests/studio_recycle_bin.test.mjs` 覆盖分类链接、类型/归属路由、种子0、转义和已删除项目提示。实际运行结果与浏览器验证只记在[维护基线](maintenance-baseline.md)，不在真实项目/资产上试恢复。

## 视频拼接条目

项目类新增assembly_clip与assembly_extension，生成类新增assembly_run；直接读取该项目JSON的removed_at，不创建另一套删除库。恢复通过/assembly/<pid>/visibility与原项目revision，父项目/片段/续写段先恢复，不自动选用或生成。当前选用及运行/待确认保护不变，已入库媒体保留。[现行说明](video-assembly.md)。

视频接续6.3.16的左侧轨道由原视频和已选成功续接投影；轨道项没有第二套删除状态。移除原视频/生成续接分别复用assembly_clip/assembly_extension，父级与下游依赖保护保持。恢复续写段不自动恢复选用，因此不会直接重返成片轨道；用户重新选用已有候选后加入，文件和旧快照保持。
