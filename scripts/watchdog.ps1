<#
.SYNOPSIS
    Restarts the TAA engine when its heartbeat goes stale (PLAN A19, A21; TAA-605).

.DESCRIPTION
    Run every minute by Task Scheduler (scripts/setup_windows_host.ps1). Reads data/heartbeat.json:
      - missing or older than -MaxAgeSeconds  -> stop the old engine process (if it is still there) and start
        a new one;
      - status "stopped"                       -> the operator stopped the engine on purpose: do nothing
        (unless -Force); "failed" (it stopped after an error) is no deliberate stop: it is restarted once
        the heartbeat is older than -MaxAgeSeconds;
      - fresh                                  -> do nothing.
    The engine itself runs PAPER only in Milestone 1; this script never changes TRADING_MODE.
    Every action is appended to logs/watchdog.log.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\watchdog.ps1 -RepoRoot C:\Users\korap\taa
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Heartbeat = "data\heartbeat.json",
    [int]$MaxAgeSeconds = 120,
    [string]$Mode = "paper",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "watchdog.log"

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"), $Message
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

$heartbeatPath = Join-Path $RepoRoot $Heartbeat
$state = $null
$ageSeconds = $null
if (Test-Path $heartbeatPath) {
    try {
        $state = Get-Content -Raw -Path $heartbeatPath | ConvertFrom-Json
        $ts = [DateTimeOffset]::Parse($state.ts)
        $ageSeconds = ([DateTimeOffset]::UtcNow - $ts).TotalSeconds
    } catch {
        Write-Log "heartbeat unreadable: $($_.Exception.Message)"
    }
}

if ($null -ne $state -and $state.status -eq "stopped" -and -not $Force) {
    exit 0  # a deliberate stop is not a failure
}
if ($null -ne $ageSeconds -and $ageSeconds -le $MaxAgeSeconds) {
    exit 0  # healthy
}

$reason = if ($null -eq $ageSeconds) { "no heartbeat" } else { "heartbeat {0:N0} s old" -f $ageSeconds }
if ($null -ne $state -and $state.pid) {
    $old = Get-Process -Id ([int]$state.pid) -ErrorAction SilentlyContinue
    if ($null -ne $old -and $old.ProcessName -like "python*") {
        if ($PSCmdlet.ShouldProcess("python pid $($old.Id)", "Stop stalled engine")) {
            Write-Log "stopping stalled engine pid $($old.Id) ($reason)"
            Stop-Process -Id $old.Id -Force -Confirm:$false
        }
    }
}

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Log "cannot restart: $python not found"
    exit 1
}
if ($PSCmdlet.ShouldProcess("TAA engine", "Start ($reason)")) {
    Write-Log "starting engine ($reason)"
    Start-Process -FilePath $python -ArgumentList @("-m", "app.main", "--mode", $Mode) `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden
}
