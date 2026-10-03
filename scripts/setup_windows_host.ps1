<#
.SYNOPSIS
    Registers the TAA engine and its watchdog in Windows Task Scheduler (PLAN A21; TAA-605).

.DESCRIPTION
    Creates two tasks for the current user (no administrator rights, no stored password):
      - "TAA Engine":   at logon, runs  .venv\Scripts\python.exe -m app.main --mode paper
      - "TAA Watchdog": every minute, runs scripts\watchdog.ps1 (restarts a stalled engine)
    On a VPS, disconnect the RDP session instead of logging off, so the logon session keeps running.

    Run it yourself; nothing here runs automatically. Use -WhatIf to see what would be registered, and
    -Unregister to remove both tasks. Run `python -m app.cli doctor` first.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_windows_host.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Mode = "paper",
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$engineTask = "TAA Engine"
$watchdogTask = "TAA Watchdog"

if ($Unregister) {
    foreach ($name in @($engineTask, $watchdogTask)) {
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            if ($PSCmdlet.ShouldProcess($name, "Unregister scheduled task")) {
                Unregister-ScheduledTask -TaskName $name -Confirm:$false
            }
        }
    }
    exit 0
}

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python venv not found at $python (create it first: py -3.11 -m venv .venv)"
}
$user = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)

$engineAction = New-ScheduledTaskAction -Execute $python -Argument "-m app.main --mode $Mode" -WorkingDirectory $RepoRoot
$engineTrigger = New-ScheduledTaskTrigger -AtLogOn -User $user
if ($PSCmdlet.ShouldProcess($engineTask, "Register (at logon)")) {
    Register-ScheduledTask -TaskName $engineTask -Action $engineAction -Trigger $engineTrigger `
        -Principal $principal -Settings $settings -Description "TAA engine (PAPER in Milestone 1)" -Force | Out-Null
}

$watchdog = Join-Path $RepoRoot "scripts\watchdog.ps1"
$watchdogArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchdog`" -RepoRoot `"$RepoRoot`" -Mode $Mode"
$watchdogAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $watchdogArgs -WorkingDirectory $RepoRoot
$watchdogTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)
if ($PSCmdlet.ShouldProcess($watchdogTask, "Register (every minute)")) {
    Register-ScheduledTask -TaskName $watchdogTask -Action $watchdogAction -Trigger $watchdogTrigger `
        -Principal $principal -Settings $settings -Description "Restarts the TAA engine when its heartbeat is stale" -Force | Out-Null
}

Write-Output "Registered '$engineTask' (at logon) and '$watchdogTask' (every minute) for $user."
