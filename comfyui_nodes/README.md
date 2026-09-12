# 图片多图编辑配套节点

网站原两图编辑仍使用原 `comfyui-krea2edit`。3—9 图任务使用本目录的 `timeforest_krea_multiref`，将所有已选图片依 A—I 顺序送入正负语义编码及 VAE 参考条件，空位跳过，图片不拼成九宫格。它复用上游多参考 forward 和图片适配函数，不复制模型实现、不下载模型。

部署时将 `timeforest_krea_multiref` 文件夹复制到目标 ComfyUI 的 `custom_nodes`，保留原 `comfyui-krea2edit`，待无活动任务时正常重启 ComfyUI。网站后端也需要重新加载本次代码。远程引擎安装在远端；网站不会代装、代重启或静默忽略第三张以后的图片。缺少扩展时运行准备阶段会明确报错，并且不会提交 `/prompt`。

接口依据为本机 `comfyui-krea2edit` 的 `Krea2EditGroundedEncode._prep/_template`、`_fit_encode_image`、`_to_4d`、`krea2_edit_forward` 和 ComfyUI 的 diffusion wrapper。后者源码已支持任意数量 source blocks，原节点仅公开两个端口；本适配补充 A—I 端口。上游参考来源记录为 `86f886dac23013d88996e3a2e99093ba44d322fb`；运行时检查所需函数是否存在，不能据此保证任意未来版本兼容。

保持原参数：输出比例、面积、种子、采样器不变。`ref_boost_a` 作用于最后一张之前的所有参考（双图时只有 A），`ref_boost` 作用于最后一张实际参考。具体模型/LoRA 的多图效果与资源占用由用户实际生成验收。当前只做隔离端口、顺序、快照及编译检查，未加载模型、安装节点或重启生产。
