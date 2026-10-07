<#
.SYNOPSIS  Fully drive the installer (advance pages, install, wait, capture the finish page).
.DESCRIPTION ASCII-only; WM_COMMAND/IDOK for advancing; polls the install dir for completion.
#>
param(
  [Parameter(Mandatory)][string]$Installer,
  [Parameter(Mandatory)][string]$ShotPath,
  [int]$WaitSeconds = 40,
  [int]$PollSeconds = 300
)
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Cap3 {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
}
"@
function HwndOf($procId) { $p = Get-Process -Id $procId -ErrorAction SilentlyContinue; if ($p -and $p.MainWindowHandle -ne 0) { return $p.MainWindowHandle } return [IntPtr]::Zero }

$target = Join-Path $env:LOCALAPPDATA 'Programs\SugarAgent\SugarAgent.exe'
$proc = Start-Process -FilePath $Installer -PassThru
Write-Host "pid=$($proc.Id)"
$h = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline -and $h -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 500; $h = HwndOf $proc.Id }
if ($h -eq [IntPtr]::Zero) { Write-Host 'no window'; exit 1 }
Start-Sleep -Seconds 2

[void][Cap3]::PostMessage($h, 0x0111, [IntPtr]1, [IntPtr]::Zero)   # directory page -> shortcut page
Start-Sleep -Seconds 3
$h = HwndOf $proc.Id
[void][Cap3]::PostMessage($h, 0x0111, [IntPtr]1, [IntPtr]::Zero)   # shortcut page -> install
Write-Host 'install started'

$deadline = (Get-Date).AddSeconds($PollSeconds)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 5
  if (Test-Path $target) {
    $n = (Get-ChildItem (Split-Path $target) -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($n -gt 30000) { Write-Host "files=$n -> install phase done"; break }
  }
  if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { Write-Host 'installer exited'; break }
}
Start-Sleep -Seconds 8   # 等完成页渲染

$h = HwndOf $proc.Id
if ($h -ne [IntPtr]::Zero) {
  $rect = New-Object 'Cap3+RECT'
  [void][Cap3]::GetWindowRect($h, [ref]$rect)
  $bmp = New-Object System.Drawing.Bitmap ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc(); [void][Cap3]::PrintWindow($h, $hdc, 2); $g.ReleaseHdc($hdc)
  $bmp.Save($ShotPath, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
  Write-Host "captured -> $ShotPath"
} else { Write-Host 'window gone, cannot capture' }

if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) { & taskkill.exe /PID $proc.Id /T /F | Out-Null; Write-Host 'installer closed' }
Write-Host ("installed: " + (Test-Path $target))
