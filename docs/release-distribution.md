# 源码与配套工具包分发

**v6.3.35 功能状态：剧本创作模式和电影创作模式目前不可用。** 本版保留开发中的页面与代码，尚未完成完整创作流程验收。

当前网站与配套包 **v6.3.35**：[GitHub Release](https://github.com/sayuel-tech/TimeForest/releases/tag/v6.3.35) · [下载配套 ZIP](https://github.com/sayuel-tech/TimeForest/releases/download/v6.3.35/TimeForest-Companion-v6.3.35.zip) · [SHA256 校验](https://github.com/sayuel-tech/TimeForest/releases/download/v6.3.35/SHA256SUMS.txt)。无需网盘或提取码。

## 安装与升级

1. 保存工作并等待活动任务结束，备份配置、项目、外部资产库与提示词库。
2. 更新网站源码，把工具包 `install/` 内的 `h3ui/` 复制到网站根目录，保留目录结构。六份原始来源图与上一版相同，已有完整文件可保留。
3. 使用3—9图编辑时，将包内 `comfyui-custom-nodes/timeforest_krea_multiref`（源码仓库也有同一扩展）复制到目标 ComfyUI 的 `custom_nodes`。保留原 `comfyui-krea2edit`，在无活动任务时重启目标 ComfyUI。远程引擎安装在远端；仅使用两图可继续原节点。详见[多图节点说明](../comfyui_nodes/README.md)。
4. 依据模型名称清单准备所用模型与插件，按[README](../README.md#安装与启动)配置并重启网站、刷新页面。

安装包不会自动安装生成环境、下载权重、启动引擎或生成。网站源码升级与运行服务重载分别进行。

## 内容与兼容

配套包包含六份原始来源图、五个原图片工具及新增九图 API 示例、两个视频接续示例、模型和节点名称、扩展节点源码、许可与校验清单。图片示例由v6.3.35编译器离线导出，占位文件、固定种子0，不含网站的预处理、队列与候选流程。3—9图不拼贴，全部已选图按稳定字母进入两条参考路径；多图效果与资源消耗未作真实模型验收。

模型权重、凭据、真实配置、项目、用户媒体与库内容不发布。package-manifest.json校验包内文件，SHA256SUMS.txt校验ZIP。源码沿用sayuel-tech/TimeForest公开main历史；原工作流在Release附件中分发，不能把原本地维护历史合入公开仓库或误推镜像origin。仅保留原四张获准公开截图。
