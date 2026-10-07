<#
.SYNOPSIS  Launch the installer, press Enter to advance one page, capture that page, then close it.
.DESCRIPTION ASCII-only on purpose (Windows PowerShell 5.1 + BOM-less UTF-8 issue).
#>
param(
  [Parameter(Mandatory)][string]$Installer,
  [Parameter(Mandatory)][string]$ShotPath,
  [int]$WaitSeconds = 40,
  [int]$AdvanceCount = 1
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class CapWin {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
}
"@

$proc = Start-Process -FilePath $Installer -PassThru
Write-Host "pid=$($proc.Id)"
function Hwnd { $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue; if ($p -and $p.MainWindowHandle -ne 0) { return $p.MainWindowHandle }; return [IntPtr]::Zero }
$h = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline -and $h -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 500; $h = Hwnd }
if ($h -eq [IntPtr]::Zero) { Write-Host 'no window'; exit 1 }
Start-Sleep -Seconds 2

$shell = New-Object -ComObject WScript.Shell
for ($i = 0; $i -lt $AdvanceCount; $i++) {
  [void]$shell.AppActivate($proc.Id)
  Start-Sleep -Milliseconds 800
  [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
  Write-Host "sent ENTER ($($i + 1)/$AdvanceCount)"
  Start-Sleep -Seconds 2
}

$h = Hwnd
$rect = New-Object 'CapWin+RECT'
[void][CapWin]::GetWindowRect($h, [ref]$rect)
$bmp = New-Object System.Drawing.Bitmap ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc(); [void][CapWin]::PrintWindow($h, $hdc, 2); $g.ReleaseHdc($hdc)
$bmp.Save($ShotPath, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
Write-Host "captured -> $ShotPath"
& taskkill.exe /PID $proc.Id /T /F | Out-Null
Write-Host 'closed'
