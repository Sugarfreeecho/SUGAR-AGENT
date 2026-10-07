<#
.SYNOPSIS
  Launch the installer, capture ONLY its own window to a PNG, then close it.

.DESCRIPTION
  Used to verify the installer UI without installing anything: the screenshot is cropped to the
  installer window rect (no desktop content), and the process tree is killed right after capture.
  ASCII-only: Windows PowerShell 5.1 reads BOM-less UTF-8 scripts as ANSI.
#>
param(
  [Parameter(Mandatory)][string]$Installer,
  [string]$Out = (Join-Path $PSScriptRoot '..\build\installer-window.png'),
  [int]$WaitSeconds = 40,
  [int]$SettleMs = 2000,
  [string]$SendKeys = ''
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class SugarWin32 {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int maxCount);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint flags);
}
"@

$installerPath = [IO.Path]::GetFullPath($Installer)
if (-not (Test-Path -LiteralPath $installerPath)) { throw "missing installer: $installerPath" }
$Out = [IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null

Write-Host "launching $installerPath"
$proc = Start-Process -FilePath $installerPath -PassThru

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$hwnd = [IntPtr]::Zero
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 500
  $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
  if (-not $p) { break }
  $p.Refresh()
  if ($p.MainWindowHandle -ne [IntPtr]::Zero) { $hwnd = $p.MainWindowHandle; break }
}

if ($hwnd -eq [IntPtr]::Zero) {
  Write-Host 'no installer window appeared'
  try { & taskkill.exe /PID $proc.Id /T /F | Out-Null } catch { }
  exit 1
}

Write-Host "window handle=$hwnd, settling ${SettleMs}ms"
[void][SugarWin32]::ShowWindow($hwnd, 5)
[void][SugarWin32]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds $SettleMs

# 标题核对：确认抓到的是安装器窗口本身
$titleBuffer = New-Object System.Text.StringBuilder 512
[void][SugarWin32]::GetWindowTextW($hwnd, $titleBuffer, $titleBuffer.Capacity)
Write-Host ("window title = '" + $titleBuffer.ToString() + "'")

if ($SendKeys -ne '') {
  Write-Host "sending keys: $SendKeys"
  Add-Type -AssemblyName System.Windows.Forms
  [void][SugarWin32]::SetForegroundWindow($hwnd)
  Start-Sleep -Milliseconds 500
  [System.Windows.Forms.SendKeys]::SendWait($SendKeys)
  Start-Sleep -Milliseconds 1500
}

$rect = New-Object 'SugarWin32+RECT'
[void][SugarWin32]::GetWindowRect($hwnd, [ref]$rect)
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top

$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
# PrintWindow(PW_RENDERFULLCONTENT=2) 抓窗口自身内容，不受遮挡影响
$hdc = $graphics.GetHdc()
$printed = [SugarWin32]::PrintWindow($hwnd, $hdc, 2)
$graphics.ReleaseHdc($hdc)
if (-not $printed) {
  Write-Host 'PrintWindow failed, falling back to screen copy'
  $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $width, $height))
}
$bitmap.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
Write-Host "captured $width x $height -> $Out"

try { & taskkill.exe /PID $proc.Id /T /F | Out-Null } catch { }
Write-Host 'installer closed'
