<#
.SYNOPSIS
  End-to-end smoke test for the packaged desktop build.

.DESCRIPTION
  Launches the packaged SugarAgent.exe with an isolated --user-data-dir, waits for the
  embedded backend to become healthy, inspects the desktop log, then kills the process tree.
  Exit code 0 means the check passed. ASCII-only on purpose: Windows PowerShell 5.1 reads
  BOM-less UTF-8 scripts as ANSI and would mangle non-ASCII literals.
#>
param(
  [string]$AppDir = (Join-Path $PSScriptRoot '..\build\dist\win-unpacked'),
  [int]$WaitSeconds = 120
)

$ErrorActionPreference = 'Stop'
$AppDir = [IO.Path]::GetFullPath($AppDir)
$exe = Join-Path $AppDir 'SugarAgent.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "missing $exe (run: npm run dist:dir)" }

$smokeRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\build\smoke-desktop'))
$userData = Join-Path $smokeRoot 'userdata'
if (Test-Path -LiteralPath $smokeRoot) { Remove-Item -LiteralPath $smokeRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $userData | Out-Null

Write-Host "launching: $exe"
$proc = Start-Process -FilePath $exe -ArgumentList @("--user-data-dir=`"$userData`"") -PassThru
Write-Host "pid=$($proc.Id), waiting up to $WaitSeconds s ..."

$logPath = Join-Path $userData 'logs\desktop.log'
$statusPath = Join-Path $userData 'desktop-status.json'
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$port = 8192
$loadedTarget = $null
$status = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 3
  if ($proc.HasExited) { break }
  if (Test-Path -LiteralPath $statusPath) {
    try { $status = Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $status = $null }
    if ($status) {
      $port = [int]$status.port
      if ($status.windowTarget) { $loadedTarget = $status.windowTarget }
    }
  }
  if ($loadedTarget) { break }
}

$ok = $false
$detail = @()
try {
  $response = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/runtime-status" -TimeoutSec 10 -UseBasicParsing
  $detail += "health: HTTP $($response.StatusCode) on port $port"
  if ($loadedTarget) { $ok = $true }
} catch {
  $detail += "health check failed: $($_.Exception.Message)"
}

if (Test-Path -LiteralPath $logPath) {
  $detail += '--- desktop.log tail ---'
  $detail += (Get-Content -LiteralPath $logPath -Tail 15)
}

try {
  if (-not $proc.HasExited) { & taskkill.exe /PID $proc.Id /T /F | Out-Null }
} catch { }

$detail | ForEach-Object { Write-Host $_ }
if ($ok) {
  Write-Host "PASS: desktop smoke ok (window target: $loadedTarget)"
  exit 0
}
Write-Host "FAIL: desktop smoke failed"
exit 1
