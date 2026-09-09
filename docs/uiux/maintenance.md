# 索引维护与按需调阅

## 开始一项 UI/UX 工作

1. 从根 AGENTS、PROJECT_GUIDE、维护基线进入本目录 README。
2. 按用户用词找到页面卡；公共变化再读对应 common 卡。改美术读 visuals；跨模式读 workflows。
3. 查实际入口与可搜索符号。需要调用关系时，只读 maps/<专题ID>.json；它记录静态导入和实际直接导入者，动态业务关系仍查源码。
4. 在相关代码中核对当前事实，先列保留内容，再说明具体改动；历史截图只作参考。

## 改动时同批维护

- 新页面、重命名、入口迁移：更新 catalog 的 ID/关键词/doc/source_patterns/entrypoints，并补页面卡。
- 公共组件：更新对应 common 卡与受影响调用方；不能只更新某一个模式。
- 美术：保留原优秀资产。新增/改名后核对实际引用与尺寸，刷新 visuals/assets.json；认可依据人工记录，不由文件存在推断。
- 行为或已知问题变化：更新对应页面/问题记录；实际交付状态只写 maintenance-baseline，避免第二本台账。
- 新证据：记录环境、数据、时间和对应改动；不用当前生成的指纹给旧截图背书。

## 工具

从仓库根使用现有 Python：

```powershell
.\.venv\Scripts\python.exe tools/check_uiux_index.py --topic authoring
.\.venv\Scripts\python.exe tools/check_uiux_index.py
# 核对并更新页面卡/catalog 后，刷新机械关系与资源指纹；不自动修改人工判断
.\.venv\Scripts\python.exe tools/check_uiux_index.py --refresh
```

默认只读检查文件/链接、七模式覆盖、前端文件覆盖与机器图漂移；不会运行应用、读取用户数据、安装依赖或联网。--refresh 仅写 docs/uiux/maps 与 visuals/assets.json，不等于内容已复核或 UI 已验收。

此目录已加入既有 context_guard 的文档范围。该工具的 docs 字段只接受逐文件路径：新增专题、机器图或证据文档时，将文件追加到 docs/governance/context-check.json 的 uiux-index.docs；不要写通配符。索引默认检查会报告漏登记。完成语义核对后，仍按治理文档 record --reviewed，然后 check；不能通过刷新机器图或回执掩盖过时文字。不增设 Git 钩子或后台自动修改任务。
