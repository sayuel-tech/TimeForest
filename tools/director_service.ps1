param([ValidateSet('Menu','Start','Stop','Restart','Status')][string]$Action = 'Menu')

# Windows PowerShell 5.1. Dot-sourcing loads functions without taking any action.
$ErrorActionPreference = 'Stop'

function Get-DirectorSettings {
    $root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    $configPath = if ($env:H3UI_CONFIG) { [IO.Path]::GetFullPath($env:H3UI_CONFIG) } else { Join-Path $root 'config.json' }
    if (!(Test-Path -LiteralPath $configPath -PathType Leaf)) { throw "配置不存在：$configPath。请先完成原有配置，不会自动安装环境。" }
    $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $port = if ($cfg.port) { [int]$cfg.port } else { 5093 }
    if ($port -lt 1 -or $port -gt 65535) { throw '网站端口配置无效。' }
    $bindHost = if ($cfg.host) { [string]$cfg.host } else { '127.0.0.1' }
    $address = switch ($bindHost) { '0.0.0.0' {'127.0.0.1'} '::' {'[::1]'} '::1' {'[::1]'} default {$bindHost} }
    [pscustomobject]@{ Root=$root; Config=$configPath; Port=$port; Url="http://${address}:$port";
        Python=(Join-Path $root '.venv\Scripts\python.exe'); Script=(Join-Path $root 'run.py'); Logs=(Join-Path $root '.runtime\launcher') }
}

function Get-DirectorListeners($Settings) {
    # No match returns an empty list; actual CIM/network failures remain errors.
    @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $Settings.Port | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Read-DirectorHealth($Settings) {
    try { $health = Invoke-RestMethod -Uri ($Settings.Url+'/api/v5/health') -TimeoutSec 5 -Method Get }
    catch { throw "端口 $($Settings.Port) 已占用，但无法核对导演台健康信息；未操作进程。$($_.Exception.Message)" }
    if (!$health.local_server_version -or !$health.deployment -or
        [IO.Path]::GetFullPath([string]$health.deployment).TrimEnd('\','/') -ine $Settings.Root.TrimEnd('\','/')) {
        throw '该端口不是本目录的时间森林导演台；未操作进程。'
    }
    return $health
}

function Get-DirectorInstance($Settings) {
    $owners = @(Get-DirectorListeners $Settings)
    if (!$owners.Count) { return $null }
    if ($owners.Count -ne 1) { throw '端口对应多个进程，无法唯一识别导演台；未操作进程。' }
    $health = Read-DirectorHealth $Settings
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($owners[0])"
    if (!$process -or $process.Name -notmatch '^pythonw?\.exe$' -or
        $process.CommandLine -notmatch '(?i)(?:^|[\s"\\/])run\.py(?:"|\s|$)') {
        throw '监听进程不是可确认的 run.py Python 服务；未操作进程。'
    }
    [pscustomobject]@{ Id=[int]$process.ProcessId; Created=$process.CreationDate; Health=$health }
}

function Assert-DirectorIdle($Health) {
    if ($Health.busy -or @($Health.jobs | Where-Object { $_ }).Count -gt 0 -or $Health.job) {
        throw '导演台还有执行中的任务。请先在网页顶部“任务列表”停止任务，并等通道释放后再停止或重启网站。'
    }
}

function Stop-Director($Settings) {
    $instance = Get-DirectorInstance $Settings
    if (!$instance) { Write-Host '导演台已经停止。'; return }
    Assert-DirectorIdle $instance.Health
    # Recheck identity and busy state immediately before stopping this single process.
    $current = Get-DirectorInstance $Settings
    if (!$current) { Write-Host '导演台已经停止。'; return }
    if ($current.Id -ne $instance.Id -or $current.Created -ne $instance.Created) { throw '服务进程已变化，请重新选择操作。' }
    Assert-DirectorIdle $current.Health
    Stop-Process -Id $current.Id -ErrorAction Stop
    for ($i=0; $i -lt 50; $i++) {
        if (@(Get-DirectorListeners $Settings).Count -eq 0) { Write-Host '导演台服务已停止。程序、项目、资产和 ComfyUI 保留。'; return }
        Start-Sleep -Milliseconds 200
    }
    throw '端口尚未释放；没有继续启动第二个服务，请稍后重试。'
}

function Start-Director($Settings, [switch]$Restarting) {
    $existing = Get-DirectorInstance $Settings
    if ($existing) { Write-Host '导演台已在运行，打开现有页面。'; Start-Process $Settings.Url; return }
    if (!(Test-Path -LiteralPath $Settings.Python -PathType Leaf)) { throw "现有 Python 环境不存在：$($Settings.Python)。不会自动安装或升级。" }
    New-Item -ItemType Directory -Force -Path $Settings.Logs | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $stdout = Join-Path $Settings.Logs "$stamp.stdout.log"
    $stderr = Join-Path $Settings.Logs "$stamp.stderr.log"
    # Paths cannot contain a double quote on Windows. Quote each path for Start-Process.
    $arguments = '"'+$Settings.Script+'" --config "'+$Settings.Config+'" --no-browser'
    if ($Restarting) { $arguments += ' --no-startup-recovery' }
    $child = Start-Process -FilePath $Settings.Python -ArgumentList $arguments -WorkingDirectory $Settings.Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Write-Host '正在启动导演台，请稍候…'
    for ($i=0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $child.Refresh()
        if ($child.HasExited) { throw "启动进程已退出。请查看日志：$stderr" }
        if (@(Get-DirectorListeners $Settings).Count) {
            $instance = Get-DirectorInstance $Settings
            if ($instance) {
                Write-Host "导演台已就绪：$($Settings.Url)"
                if ($Restarting) { Write-Host '本次重启不自动恢复或唤醒旧队列，原任务记录保留；请在任务列表核对。' }
                Start-Process $Settings.Url
                return
            }
        }
    }
    throw "30秒内尚未就绪。没有重复启动或强制终止，请查看日志：$stderr"
}

function Invoke-DirectorAction($Settings, $Choice) {
    # Serialise menu windows so two rapid starts cannot create duplicate workers.
    $mutex = New-Object Threading.Mutex($false, "Local\TimeForest-Director-$($Settings.Port)")
    $held = $false
    try {
        try { $held = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $held = $true }
        if (!$held) { throw '另一个导演台菜单正在执行操作，请稍后再试。' }
        switch ($Choice) {
            'Start' { Start-Director $Settings }
            'Stop' { Stop-Director $Settings }
            'Restart' { Stop-Director $Settings; Start-Director $Settings -Restarting }
            'Status' {
                $instance = Get-DirectorInstance $Settings
                if ($instance) { Write-Host "导演台运行中：$($Settings.Url) · PID $($instance.Id)" }
                else { Write-Host '导演台未运行。' }
            }
        }
    } finally { if ($held) { $mutex.ReleaseMutex() }; $mutex.Dispose() }
}

function Show-DirectorMenu {
    while ($true) {
        Write-Host "`n============ 时间森林导演台 ============"
        Write-Host '  1. 启动导演台'
        Write-Host '  2. 停止导演台（保留程序和数据）'
        Write-Host '  3. 重启导演台'
        Write-Host '  0. 退出菜单'
        Write-Host '关闭本菜单不会停止后台服务。停止/重启前请保存网页编辑。'
        $choice = Read-Host '请选择 [0-3]'
        if ($choice -eq '0') { return }
        $selected = switch ($choice) { '1' {'Start'} '2' {'Stop'} '3' {'Restart'} default {$null} }
        if (!$selected) { Write-Host '请输入 0、1、2 或 3。'; continue }
        try { Invoke-DirectorAction (Get-DirectorSettings) $selected }
        catch { Write-Host ("操作未完成："+$_.Exception.Message) -ForegroundColor Red }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        if ($Action -eq 'Menu') { Show-DirectorMenu }
        else { Invoke-DirectorAction (Get-DirectorSettings) $Action }
    } catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }
}
