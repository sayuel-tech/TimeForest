# 源码与配套工具包分发

**v6.3.33 功能状态：剧本创作模式和电影创作模式目前不可用。** 本版保留开发中的页面与代码，尚未完成可用性与完整创作流程验收；请勿将这两个模式视为已交付功能。后续状态以版本说明为准。

当前版本 **v6.3.33**：[GitHub Release](https://github.com/sayuel-tech/TimeForest/releases/tag/v6.3.33) · [下载配套 ZIP](https://github.com/sayuel-tech/TimeForest/releases/download/v6.3.33/TimeForest-Companion-v6.3.33.zip) · [SHA256 校验](https://github.com/sayuel-tech/TimeForest/releases/download/v6.3.33/SHA256SUMS.txt)。本版无需夸克网盘或提取码。

源码保留在 Git 仓库；工作流与模型名称 TXT 独立压缩，作为同版 GitHub Release 附件提供。用户已于 2026-09-09 明确授权代码和配套包一并更新到 GitHub，替代此前只在夸克分发的限制。模型权重、凭据、真实配置、项目、资产与提示词库内容不发布。

## 安装与升级

1. 下载网站同版源码与上方配套 ZIP，解压。
2. 将工具包 `install/` 内的 `h3ui/` 复制到网站根目录，保留目录结构。不要把整个 `install/` 目录放进去。
3. 补齐 `h3ui/studio_sources/` 中的 `dance.json`、`official_r2v.json`、`official_t2v.json`、`wenxi.json`、`impact.json`，以及 `h3ui/image_studio/sources/krea-edit.json`。
4. 根据模型选用名称 TXT 准备所用工作流需要的模型与插件，再按 [README](../README.md#安装与启动) 配置和启动网站。可选或旁路项不代表全部必装。

升级前保存工作、等待活动任务结束，备份自己的配置、项目、外部资产库及提示词库。更新网站代码后重启网站并刷新页面。安装配套包不会自动安装生成环境、启动引擎或生成。

## 内容与兼容

配套包包含六份原始来源图、五个图片 API 示例、两个视频接续 API 示例、模型名称、节点类型、使用说明、许可与校验清单。六份来源图与 v6.3.20 相同；API 示例由本版编译器离线导出，使用占位输入、固定种子和通用描述。它们不包含网站的完整调度、预处理和项目流程。

已有完整来源图可以继续使用；替换工具包不会升级网站功能。包中不包含模型权重或用户媒体。`package-manifest.json` 核对包内文件；Release 同页的 `SHA256SUMS.txt` 核对整个 ZIP。

## 发布维护边界

沿用 sayuel-tech/TimeForest 已公开 main 历史，不能把包含个人维护资料的原仓库历史合入公开仓库，也不能向原镜像 origin 推送。原始图和 ZIP 由 Release 附件分发，公开 Git 树的忽略和检查规则仍保护它们，避免误提交安装后的本地文件。

发布前核对公开文件与压缩包，排除运行目录、prompt_library、prompt_receipts、自定义库目录及备份；节点目录保留声明结构并移除扫描得到的个人文件名。在临时目录组合源码与配套图，完成离线及隔离检查，不运行生产服务或 ComfyUI。

更新日志见 [CHANGELOG](../CHANGELOG.md)。v6.3.20 曾使用夸克网盘，其旧日志是历史记录；当前安装统一以上方 GitHub Release 为准。常规开发不自动授权下一次发布。
