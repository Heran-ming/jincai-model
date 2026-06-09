param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [int]$MaxMatches = 40
)

$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $RepoRoot

$logDir = Join-Path $RepoRoot "records\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "odds_monitor.log"

$startedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
"[$startedAt] start odds monitor" | Tee-Object -FilePath $logPath -Append | Out-Null

try {
    python "scripts\collect_500_snapshots.py" --max-matches $MaxMatches 2>&1 |
        Tee-Object -FilePath $logPath -Append
    python "scripts\build_match_database.py" 2>&1 |
        Tee-Object -FilePath $logPath -Append
    $finishedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
    "[$finishedAt] completed odds monitor" | Tee-Object -FilePath $logPath -Append | Out-Null
}
catch {
    $failedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
    "[$failedAt] failed odds monitor: $($_.Exception.Message)" |
        Tee-Object -FilePath $logPath -Append | Out-Null
    throw
}
