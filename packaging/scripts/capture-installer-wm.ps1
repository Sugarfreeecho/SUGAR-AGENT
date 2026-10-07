<#
.SYNOPSIS  Launch installer, advance one page via WM_COMMAND/IDOK, capture that page, close.
.DESCRIPTION ASCII-only. WM_COMMAND/IDOK proved reliable where SendKeys did not.
#>
param(
  [Parameter(Mandatory)][string]$Installer,
  [Parameter(Mandatory)][string]$ShotPath,
  [int]$WaitSeconds = 40
)
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Cap2 {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
}
"@
$proc = Start-Process -FilePath $Installer -PassThru
function HwndOf($procId) { $p = Get-Process -Id $procId -ErrorAction SilentlyContinue; if ($p -and $p.MainWindowHandle -ne 0) { return $p.MainWindowHandle } return [IntPtr]::Zero }
$h = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline -and $h -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 500; $h = HwndOf $proc.Id }
if ($h -eq [IntPtr]::Zero) { Write-Host 'no window'; exit 1 }
Start-Sleep -Seconds 2
[void][Cap2]::PostMessage($h, 0x0111, [IntPtr]1, [IntPtr]::Zero)   # WM_COMMAND / IDOK
Start-Sleep -Seconds 3
$h = HwndOf $proc.Id
$rect = New-Object 'Cap2+RECT'
[void][Cap2]::GetWindowRect($h, [ref]$rect)
$bmp = New-Object System.Drawing.Bitmap ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc(); [void][Cap2]::PrintWindow($h, $hdc, 2); $g.ReleaseHdc($hdc)
$bmp.Save($ShotPath, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
Write-Host "captured -> $ShotPath"
& taskkill.exe /PID $proc.Id /T /F | Out-Null
Write-Host 'closed'
