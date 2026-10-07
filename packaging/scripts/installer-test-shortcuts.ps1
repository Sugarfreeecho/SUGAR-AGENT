<#
.SYNOPSIS  Minimal end-to-end installer test: advance to the shortcut page, optionally uncheck the
          desktop shortcut, start the install, then poll until the app files land on disk.
.DESCRIPTION  ASCII-only; Chinese labels built from [char] codes so PowerShell 5.1 cannot mangle them.
#>
param(
  [Parameter(Mandatory)][string]$Installer,
  [switch]$UncheckDesktop,
  [int]$WaitSeconds = 40,
  [int]$PollSeconds = 300
)
$ErrorActionPreference = 'Continue'
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public class Dlg2 {
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int max);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr param);
  public delegate bool EnumProc(IntPtr hWnd, IntPtr param);
  public static IntPtr Find(IntPtr parent, string prefix) {
    IntPtr result = IntPtr.Zero;
    EnumChildWindows(parent, (hwnd, param) => {
      var sb = new StringBuilder(512);
      GetWindowTextW(hwnd, sb, sb.Capacity);
      if (sb.Length > 0 && sb.ToString().StartsWith(prefix)) { result = hwnd; return false; }
      return true;
    }, IntPtr.Zero);
    return result;
  }
}
"@

$WM_COMMAND = 0x0111; $IDOK = 1; $BM_SETCHECK = 0x00F1; $BM_GETCHECK = 0x00F0
$labelDesktop = -join ([char]0x521B,[char]0x5EFA,[char]0x684C,[char]0x9762,[char]0x5FEB,[char]0x6377,[char]0x65B9,[char]0x5F0F)

function HwndOf($procId) {
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if ($p -and $p.MainWindowHandle -ne 0) { return $p.MainWindowHandle }
  return [IntPtr]::Zero
}

$target = Join-Path $env:LOCALAPPDATA 'Programs\SugarAgent\SugarAgent.exe'
$proc = Start-Process -FilePath $Installer -PassThru
Write-Host "pid=$($proc.Id)"
$h = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline -and $h -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 500; $h = HwndOf $proc.Id }
if ($h -eq [IntPtr]::Zero) { Write-Host 'no window'; exit 1 }
Start-Sleep -Seconds 2

[void][Dlg2]::PostMessage($h, $WM_COMMAND, [IntPtr]$IDOK, [IntPtr]::Zero)   # 位置页 -> 下一步
$box = [IntPtr]::Zero
$h2 = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds(25)
while ((Get-Date) -lt $deadline -and $box -eq [IntPtr]::Zero) {
  Start-Sleep -Milliseconds 700
  $h2 = HwndOf $proc.Id
  if ($h2 -ne [IntPtr]::Zero) { $box = [Dlg2]::Find($h2, $labelDesktop) }
}
Write-Host "desktop checkbox: $box"
if ($box -ne [IntPtr]::Zero) {
  Write-Host ("check-state before: " + [int][Dlg2]::SendMessage($box, $BM_GETCHECK, [IntPtr]::Zero, [IntPtr]::Zero))
  if ($UncheckDesktop) {
    [void][Dlg2]::SendMessage($box, $BM_SETCHECK, [IntPtr]0, [IntPtr]::Zero)
    Write-Host ("check-state after uncheck: " + [int][Dlg2]::SendMessage($box, $BM_GETCHECK, [IntPtr]::Zero, [IntPtr]::Zero))
  }
}

[void][Dlg2]::PostMessage($h2, $WM_COMMAND, [IntPtr]$IDOK, [IntPtr]::Zero)   # 开始安装
Write-Host 'clicked install, polling for files...'

$deadline = (Get-Date).AddSeconds($PollSeconds)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 5
  if (Test-Path $target) {
    $n = (Get-ChildItem (Split-Path $target) -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Host ("  files in install dir: $n")
    if ($n -gt 30000) { Write-Host 'install looks complete'; break }
  }
  if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { Write-Host 'installer exited'; break }
}

Start-Sleep -Seconds 5
Write-Host '--- shortcuts ---'
Write-Host ("desktop   : " + (Test-Path (Join-Path $env:USERPROFILE 'Desktop\SugarAgent.lnk')))
Write-Host ("start menu: " + (Test-Path (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\SugarAgent.lnk')))
Write-Host ("installed : " + (Test-Path $target))
if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) { & taskkill.exe /PID $proc.Id /T /F | Out-Null; Write-Host 'installer closed' }
