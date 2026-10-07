<#
.SYNOPSIS
    Runs the local -Mt5 demo stack (web, worker, engine) from Windows Task Scheduler instead of console windows.

.DESCRIPTION
    Processes started from a terminal or a coding-assistant session die with that session. Started by Task
    Scheduler they do not: each part runs as its own task under the current user (interactive, no stored
    password, no administrator rights), at logon and on demand.

      -Register    creates "TAA Demo web", "TAA Demo worker", "TAA Demo engine" (at logon, the engine 60 s after
                   the web) and "TAA Demo check" (every 5 minutes: starts a part whose health endpoint does
                   not answer; an engine whose heartbeat says "stopped" was stopped on purpose and is left
                   alone, unless -Force; "failed" means it stopped after an error and is started again)
      -Start       starts the three part tasks now (web first, then worker, then engine) and enables
                   "TAA Demo check" again
      -Stop        stops the three part tasks and ends their python processes (a stopped task only ends its
                   powershell.exe; the python children it started would keep running), and disables
                   "TAA Demo check" so it does not start the stack again; the engine reconciles at the next start
      -Check       what "TAA Demo check" runs
      -Unregister  removes the four tasks

    Every part runs scripts\start-demo.ps1 -Role <part> -Mt5 [-Demo], so the databases, ports and .env.demo-mt5
    are exactly those of scripts\start-demo.cmd -Mt5 [-Demo]. -Demo (default on) makes the engine send DEMO
    orders to the demo account (see docs\RUNBOOK_DEMO.md); -Demo:$false keeps it PAPER. Actions go to
    logs\demo-tasks.log.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo-tasks.ps1 -Register
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo-tasks.ps1 -Start
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo-tasks.ps1 -Check -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Register,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Check,
    [switch]$Unregister,
    [switch]$Demo = $true,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Parts = @("web", "worker", "engine")
$CheckTask = "TAA Demo check"
$WebHealth = "http://localhost:8001/api/v1/health"
$EngineHealth = "http://127.0.0.1:8766/health"
$Heartbeat = Join-Path $Root "data\demo\heartbeat-mt5.json"
$LogFile = Join-Path $Root "logs\demo-tasks.log"

function TaskName([string]$part) { "TAA Demo $part" }

function Log([string]$message) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogFile) | Out-Null
    $line = "$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')) $message"
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Output $line
}

function Answers([string]$url) {
    try { return (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri $url).StatusCode -eq 200 } catch { return $false }
}

function StoppedOnPurpose {
    if (-not (Test-Path $Heartbeat)) { return $false }
    try { return ((Get-Content $Heartbeat -Raw | ConvertFrom-Json).status -eq "stopped") } catch { return $false }
}

# The processes a part's task started: its powershell.exe (start-demo.ps1 -Role <part> -Mt5) and everything
# below it (the venv launcher and the real python). Matched on the command line, so the FakeMT5 stack
# (start-demo.cmd without -Mt5) and other python processes are never touched.
function PartTree([string]$part) {
    $all = @(Get-CimInstance Win32_Process)
    $roots = @($all | Where-Object {
            $_.Name -eq "powershell.exe" -and $_.CommandLine -match "start-demo\.ps1" -and
            $_.CommandLine -match "-Role $part\b" -and $_.CommandLine -match "-Mt5\b"
        })
    $tree = @()
    $queue = [System.Collections.Generic.Queue[object]]::new()
    foreach ($r in $roots) { $queue.Enqueue($r) }
    while ($queue.Count -gt 0) {
        $p = $queue.Dequeue()
        $tree += $p
        foreach ($child in $all | Where-Object { $_.ParentProcessId -eq $p.ProcessId }) { $queue.Enqueue($child) }
    }
    return $tree
}

function StopPart([string]$part) {
    $name = TaskName $part
    if (-not $PSCmdlet.ShouldProcess($name, "Stop scheduled task and end its processes")) { return }
    $tree = @(PartTree $part)  # read before the task stops: its powershell.exe links the tree together
    Stop-ScheduledTask -TaskName $name
    foreach ($p in $tree) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Log "stopped $name ($($tree.Count) process(es) ended)"
}

function StartPart([string]$part) {
    $name = TaskName $part
    if ($PSCmdlet.ShouldProcess($name, "Start scheduled task")) {
        Start-ScheduledTask -TaskName $name
        Log "started $name"
    }
}

if ($Unregister) {
    foreach ($name in @($Parts | ForEach-Object { TaskName $_ }) + $CheckTask) {
        if ((Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) -and $PSCmdlet.ShouldProcess($name, "Unregister")) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Log "unregistered $name"
        }
    }
    exit 0
}

if ($Register) {
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
    $script = Join-Path $PSScriptRoot "start-demo.ps1"
    $delay = @{ web = "PT0S"; worker = "PT20S"; engine = "PT60S" }
    foreach ($part in $Parts) {
        $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Role $part -Mt5"
        if ($Demo) { $arguments += " -Demo" }
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $Root
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
        $trigger.Delay = $delay[$part]
        if ($PSCmdlet.ShouldProcess((TaskName $part), "Register (at logon)")) {
            Register-ScheduledTask -TaskName (TaskName $part) -Action $action -Trigger $trigger -Principal $principal `
                -Settings $settings -Description "TAA local -Mt5 demo stack: $part (scripts\demo-tasks.ps1)" -Force | Out-Null
            Log "registered $(TaskName $part)"
        }
    }
    $checkArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Check"
    $checkAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $checkArgs -WorkingDirectory $Root
    $checkTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
        -RepetitionInterval (New-TimeSpan -Minutes 5)
    if ($PSCmdlet.ShouldProcess($CheckTask, "Register (every 5 minutes)")) {
        Register-ScheduledTask -TaskName $CheckTask -Action $checkAction -Trigger $checkTrigger -Principal $principal `
            -Settings $settings -Description "Starts a TAA demo part whose health check fails" -Force | Out-Null
        Log "registered $CheckTask"
    }
    exit 0
}

if ($Stop) {
    if ((Get-ScheduledTask -TaskName $CheckTask -ErrorAction SilentlyContinue) -and
        $PSCmdlet.ShouldProcess($CheckTask, "Disable")) {
        Disable-ScheduledTask -TaskName $CheckTask | Out-Null
        Log "disabled $CheckTask"
    }
    foreach ($part in @("engine", "worker", "web")) { StopPart $part }
    exit 0
}

if ($Start) {
    if ((Get-ScheduledTask -TaskName $CheckTask -ErrorAction SilentlyContinue) -and
        $PSCmdlet.ShouldProcess($CheckTask, "Enable")) {
        Enable-ScheduledTask -TaskName $CheckTask | Out-Null
        Log "enabled $CheckTask"
    }
    StartPart "web"
    for ($i = 0; $i -lt 30 -and -not (Answers $WebHealth); $i++) { Start-Sleep -Seconds 2 }
    StartPart "worker"
    StartPart "engine"
    exit 0
}

if ($Check) {
    if (-not (Answers $WebHealth)) {
        StartPart "web"
        StartPart "worker"  # IgnoreNew: a worker that still runs is left alone
    }
    if (-not (Answers $EngineHealth)) {
        if ((StoppedOnPurpose) -and -not $Force) {
            Log "engine heartbeat says stopped: left alone"
        } else {
            StartPart "engine"
        }
    }
    exit 0
}

Write-Output "Nothing to do: pass -Register, -Start, -Stop, -Check or -Unregister (see Get-Help $PSCommandPath)."
