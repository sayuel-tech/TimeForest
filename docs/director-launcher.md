# 桌面启动、停止与重启菜单

双击 `<本地维护路径>`，由仓库 `tools/director-menu.cmd` 调用 `tools/director_service.ps1`。菜单为：

1. 启动导演台：已有本目录服务时只打开页面；否则使用现有 `.venv/Scripts/python.exe` 启动 `run.py`，等待健康响应后打开页面。
2. 停止导演台（保留程序和数据）：按用户澄清，“卸载”指停止服务，不删除任何文件或数据。仅停止准确识别的导演台监听进程，ComfyUI独立运行。
3. 重启导演台：停止网站进程后重新加载代码，使用 `--no-startup-recovery` 跳过本次旧任务自动恢复/唤醒，原记录保留。之后到任务列表核对待处理任务。
0. 退出菜单：后台网站继续运行，关闭 CMD 也不会停止服务。

停止/重启前先保存网页编辑。有执行中 lease 时拒绝操作，需在网页顶部“任务列表”停止对应任务并等通道释放；不通过杀掉所有 Python 或关闭 ComfyUI 实现停止。端口占用但健康响应不是本目录、进程不是 Python run.py、多个监听进程或 PID/创建时间改变，也拒绝操作。

配置读取现有 `config.json`，尊重 `H3UI_CONFIG`；无额外端口配置副本。当前配置为 `127.0.0.1:5093`。绑定通配地址时浏览器使用相应回环地址。脚本不改原配置、默认生成参数、环境或数据库。缺 Python/配置时明确报错，不自动运行 setup 或安装升级。普通启动保留原启动恢复语义；维护重启的恢复开关只作用于当次进程。

服务隐藏运行，启动输出保存在 `.runtime/launcher/<时间>.stdout.log` 和 `.stderr.log`，该目录已加入 Git 忽略。启动超时或异常显示日志路径；多菜单通过同端口互斥锁串行操作。Windows PowerShell脚本为 UTF-8 BOM，CMD为ASCII及CRLF，中文菜单在Windows PowerShell 5.1可读；`ExecutionPolicy Bypass` 只用于本次调用，不改变系统执行策略。

原 `start.bat` 保持原行为，其他旧入口兼容。桌面新入口与仓库菜单是新增管理入口；若仓库迁移，更新桌面 CMD 的两处绝对路径即可，仓库脚本通过自身位置解析根目录。

维护检查：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/director_service.tests.ps1` 使用命令替身验证进程归属、忙碌/重复/重启及配置规则，不启停真实服务。桌面菜单可输入0退出以验收完整调用链；`tools/director_service.ps1 -Action Status` 仅核对监听与健康响应。实际启停/重启不是这些模拟检查的成绩，交付状态见 [维护基线](maintenance-baseline.md)。
