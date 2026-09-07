# Isolated command mocks: no real service starts/stops, browser or configuration writes.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '..\tools\director_service.ps1')
$script:passed=0
function Assert-True($value,$message) { if (!$value) { throw "FAIL: $message" }; $script:passed++ }
function Assert-Rejected([scriptblock]$operation) {
    $rejected=$false
    try { & $operation } catch { $rejected=$true }
    Assert-True $rejected 'unsafe operation must be rejected'
}
$settings=[pscustomobject]@{Root='C:\Fixture Space\Director';Port=5199;Url='http://127.0.0.1:5199';Python='C:\Fixture Space\Director\.venv\Scripts\python.exe';Script='C:\Fixture Space\Director\run.py';Config='C:\Fixture Space\Director\config.json';Logs='C:\Fixture Space\Director\.runtime\launcher'}
function Reset-Fixture {
    $script:owners=@();$script:stopped=@();$script:started=@();$script:queries=0;$script:replace=$false
    $script:health=[pscustomobject]@{local_server_version=1;deployment=$settings.Root;busy=$false;jobs=@();job=$null}
    $script:processName='python.exe'
}
function Get-NetTCPConnection { @($script:owners | ForEach-Object { [pscustomobject]@{LocalPort=5199;OwningProcess=$_} }) }
function Invoke-RestMethod { return $script:health }
function Get-CimInstance {
    $script:queries++
    [pscustomobject]@{ProcessId=47;Name=$script:processName;CreationDate=if($script:replace -and $script:queries -gt 1){'changed'}else{'original'};CommandLine='"C:\Fixture Space\Director\.venv\Scripts\python.exe" "C:\Fixture Space\Director\run.py"'}
}
function Stop-Process { param($Id);$script:stopped+=@($Id);$script:owners=@() }
function Start-Process {
    param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,[switch]$PassThru,$RedirectStandardOutput,$RedirectStandardError)
    $script:started+=@([pscustomobject]@{File=$FilePath;Arguments=$ArgumentList;Window=$WindowStyle})
    if ($PassThru) {
        $script:owners=@(47)
        $child=[pscustomobject]@{HasExited=$false}
        $child | Add-Member -MemberType ScriptMethod -Name Refresh -Value {}
        return $child
    }
}
function Start-Sleep {}
function Test-Path { return $true }
function New-Item {}

Reset-Fixture
Stop-Director $settings
Assert-True ($script:stopped.Count -eq 0) 'already stopped is idempotent'

Reset-Fixture;$script:owners=@(47)
Stop-Director $settings
Assert-True ($script:stopped.Count -eq 1 -and $script:stopped[0] -eq 47) 'only the exact identified website PID is stopped'

Reset-Fixture;$script:owners=@(47);$script:health.busy=$true
Assert-Rejected { Invoke-DirectorAction $settings 'Restart' }
Assert-True ($script:stopped.Count -eq 0 -and $script:started.Count -eq 0) 'busy restart has no process effect'

Reset-Fixture;$script:owners=@(47);$script:health.deployment='C:\Somewhere Else'
Assert-Rejected { Stop-Director $settings }
Assert-True ($script:stopped.Count -eq 0) 'foreign app is never stopped'

Reset-Fixture;$script:owners=@(47);$script:processName='comfy.exe'
Assert-Rejected { Stop-Director $settings }
Assert-True ($script:stopped.Count -eq 0) 'non-Python process refused'

Reset-Fixture;$script:owners=@(47);$script:replace=$true
Assert-Rejected { Stop-Director $settings }
Assert-True ($script:stopped.Count -eq 0) 'PID creation time must still match'

Reset-Fixture;$script:owners=@(47,48)
Assert-Rejected { Start-Director $settings }
Assert-True ($script:started.Count -eq 0) 'ambiguous listeners do not start a second service'

Reset-Fixture
Start-Director $settings
Start-Director $settings
$launches=@($script:started | Where-Object File -eq $settings.Python)
Assert-True ($launches.Count -eq 1) 'two starts launch only one service'
Assert-True ($launches[0].Window -eq 'Hidden') 'background service stays hidden'
Assert-True ($launches[0].Arguments -like '*"C:\Fixture Space\Director\run.py" --config "C:\Fixture Space\Director\config.json" --no-browser') 'paths with spaces are individually quoted'
Assert-True ($launches[0].Arguments -notlike '*--no-startup-recovery*') 'ordinary start retains original recovery behavior'

Reset-Fixture;$script:owners=@(47)
Invoke-DirectorAction $settings 'Restart'
$launches=@($script:started | Where-Object File -eq $settings.Python)
Assert-True ($script:stopped.Count -eq 1 -and $launches.Count -eq 1) 'restart stops then starts once'
Assert-True ($launches[0].Arguments -like '*--no-startup-recovery') 'maintenance restart does not wake old queues'

# Settings are parsed from a fake config response, not the production config.
function Get-Content { '{"port":5271,"host":"0.0.0.0"}' }
$parsed=Get-DirectorSettings
Assert-True ($parsed.Port -eq 5271 -and $parsed.Url -eq 'http://127.0.0.1:5271') 'configured port and local URL are used'
Write-Host "PASS: $script:passed assertions; no actual service or data modified."
