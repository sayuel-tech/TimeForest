# 当前配置样例

`llm-providers.example.json`只有DeepSeek Chat的当前初始配置，准确ID已填写，enabled=false且无credential。用户后续自行提供凭据/选择参数才启用；本轮开发不实际请求。

`provider-runtime-policy.json`决定当前可实现与保留范围；`deepseek-beta-notice.json`只保存日期级提示，不硬编码精确停机时刻。模型ID可编辑，列表不是白名单，无自动fallback。

`development-policy.json`只适用于隔离fixture，不能覆盖生产配置。`live-authorization.example.json`是未来明确测试范围记录，不是可执行授权，也不是日常用户必填的产品表单。

本地LM Studio样例在`预留设计/`，当前不启用运行适配。H3 profile从现有真实工作流解析，示例不是新节点图，不覆盖现有默认值。
