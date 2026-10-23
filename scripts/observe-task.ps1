<#
.SYNOPSIS
    Runs the market observer (research\2026-10-23-entry\observe.py) every hour of the trading day from Windows
    Task Scheduler.

.DESCRIPTION
    Owner 2026-10-23: the bot must always observe and remember price, even when no one is trading. The observer
    refreshes the XAUUSD bars from MT5 READ-ONLY (scripts\download_history.py), scores the previous hour, reads the
    market with the bot's readers and appends to research\2026-10-23-entry\diary\. It never trades.

      -Register    creates "TAA Observer": Monday to Friday, 06:05 to 23:05 Thai, every hour (the current user,
                   interactive, no stored password, no administrator rights); the PC must be awake
      -Run         what the task runs: one observation, output appended to logs\observe.log
      -Unregister  removes the task

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\observe-task.ps1 -Register
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\observe-task.ps1 -Run
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Register,
    [switch]$Run,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TaskName = "TAA Observer"
$LogFile = Join-Path $Root "logs\observe.log"

if ($Run) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogFile) | Out-Null
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    $script = Join-Path $Root "research\2026-10-23-entry\observe.py"
    Add-Content -Path $LogFile -Value "--- $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')) observe" -Encoding utf8
    $env:PYTHONIOENCODING = "utf-8"
    # cmd appends the bytes as they are (PowerShell 5.1's *>> would write UTF-16)
    cmd /c "`"$python`" `"$script`" >> `"$LogFile`" 2>&1"
    Add-Content -Path $LogFile -Value "--- exit $LASTEXITCODE" -Encoding utf8
    exit $LASTEXITCODE
}

if ($Register) {
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    $arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Run"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At "06:05"
    $repeat = New-ScheduledTaskTrigger -Once -At "06:05" -RepetitionInterval (New-TimeSpan -Hours 1) `
        -RepetitionDuration (New-TimeSpan -Hours 17 -Minutes 30)
    $trigger.Repetition = $repeat.Repetition
    if ($PSCmdlet.ShouldProcess($TaskName, "register")) {
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
            -Settings $settings -Description "TAA: hourly read-only market observation (observe.py)" -Force | Out-Null
        Write-Output "registered '$TaskName': Mon-Fri 06:05-23:05 every hour; log $LogFile"
    }
}

if ($Unregister) {
    if ($PSCmdlet.ShouldProcess($TaskName, "unregister")) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output "removed '$TaskName'"
    }
}
