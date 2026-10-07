<#
.SYNOPSIS  Drive the SugarAgent installer end to end without a human: advance pages, optionally
          uncheck the desktop-shortcut checkbox, capture the shortcut page, finish the install.
.DESCRIPTION
  Uses Win32 messages (WM_COMMAND/IDOK, BM_SETCHECK/BM_GETCHECK) on the NSIS dialog, which is far
  more reliable than SendKeys. ASCII-only source on purpose; Chinese labels are built from
  [char] codes so Windows PowerShell 5.1 cannot mangle them.
#>
param(
  [Parameter(Mandatory)][string]$Installer,
  [string]$ShotPath = '',
  [switch]$UncheckDesktop,
  [int]$WaitSeconds = 40,
  [int]$InstallTimeoutSeconds = 420
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public class Dlg {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int max);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr param);
  public delegate bool EnumProc(IntPtr hWnd, IntPtr param);

  public static List<string> Children(IntPtr parent) {
    var found = new List<string>();
    EnumChildWindows(parent, (hwnd, param) => {
      var sb = new StringBuilder(512);
      GetWindowTextW(hwnd, sb, sb.Capacity);
      if (sb.Length > 0) found.Add(hwnd.ToInt64().ToString() + "|" + sb.ToString());
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static IntPtr FindChildByTextPrefix(IntPtr parent, string prefix) {
    IntPtr result = IntPtr.Zero;
    EnumChildWindows(parent, (hwnd, param) => {
      var sb = new StringBuilder(512);
      GetWindowTextW(hwnd, sb, sb.Capacity);
      if (sb.Length > 0 && sb.ToString().StartsWith(prefix)) { result = hwnd; return false; }
      return true;
    }, IntPtr.Zero);
    return result;
  }
  public static string TextOf(IntPtr hwnd) {
    var sb = new StringBuilder(512);
    GetWindowTextW(hwnd, sb, sb.Capacity);
    return sb.ToString();
  }
}
"@

$WM_COMMAND     = 0x0111
$IDOK           = 1
$BM_SETCHECK    = 0x00F1
$BM_GETCHECK    = 0x00F0
$WM_LBUTTONDOWN = 0x0201
$WM_LBUTTONUP   = 0x0202
$BST_UNCHECKED  = 0

# Chinese labels from code points (avoids any file-encoding dependency)
$labelDesktop = -join ([char]0x521B,[char]0x5EFA,[char]0x684C,[char]0x9762,[char]0x5FEB,[char]0x6377,[char]0x65B9,[char]0x5F0F)   # 创建桌面快捷方式
$labelFinish = -join ([char]0x5B8C,[char]0x6210)                                                                                  # 完成

function Get-InstallerWindow($procId) {
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if ($p -and $p.MainWindowHandle -ne 0) { return $p.MainWindowHandle }
  return [IntPtr]::Zero
}
function Capture($hwnd, $path) {
  $rect = New-Object 'Dlg+RECT'
  [void][Dlg]::GetWindowRect($hwnd, [ref]$rect)
  $bmp = New-Object System.Drawing.Bitmap ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc(); [void][Dlg]::PrintWindow($hwnd, $hdc, 2); $g.ReleaseHdc($hdc)
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
  Write-Host "captured -> $path"
}
function Click-Default($hwnd) { [void][Dlg]::PostMessage($hwnd, $WM_COMMAND, [IntPtr]$IDOK, [IntPtr]::Zero) }

$proc = Start-Process -FilePath $Installer -PassThru
Write-Host "installer pid=$($proc.Id)"
$hwnd = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline -and $hwnd -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 500; $hwnd = Get-InstallerWindow $proc.Id }
if ($hwnd -eq [IntPtr]::Zero) { Write-Host 'no installer window'; exit 1 }
Start-Sleep -Seconds 2

# 第 1 页：选定安装位置 -> 下一步
$before = [Dlg]::Children($hwnd).Count
Click-Default $hwnd
Start-Sleep -Seconds 3

# 第 2 页：自定义“快捷方式选项”页
$hwnd = Get-InstallerWindow $proc.Id
$texts = [Dlg]::Children($hwnd)
$after = $texts.Count
Write-Host "child controls: before=$before after=$after"
foreach ($t in $texts) { Write-Host ("   " + $t.Split('|')[1]) }
if ($ShotPath -ne '') { Capture $hwnd $ShotPath }

$box = [Dlg]::FindChildByTextPrefix($hwnd, $labelDesktop)
Write-Host "desktop checkbox hwnd: $box"
if ($box -ne [IntPtr]::Zero) {
  $state = [int][Dlg]::SendMessage($box, $BM_GETCHECK, [IntPtr]::Zero, [IntPtr]::Zero)
  Write-Host "initial desktop checkbox check-state: $state (1=checked)"
  if ($UncheckDesktop) {
    [void][Dlg]::SendMessage($box, $BM_SETCHECK, [IntPtr]$BST_UNCHECKED, [IntPtr]::Zero)
    $state = [int][Dlg]::SendMessage($box, $BM_GETCHECK, [IntPtr]::Zero, [IntPtr]::Zero)
    Write-Host "after uncheck, check-state: $state (0=unchecked)"
  }
} else {
  Write-Host 'WARNING: desktop checkbox not found on this page'
}

# 开始安装
Click-Default $hwnd
Write-Host 'clicked install'
Start-Sleep -Seconds 3

# 等安装完成：轮询窗口里是否出现“完成”按钮
$finished = $false
$deadline = (Get-Date).AddSeconds($InstallTimeoutSeconds)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 3
  if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { Write-Host 'installer process exited'; break }
  $h = Get-InstallerWindow $proc.Id
  # 安装过程中主窗口句柄可能短暂为 0，不能据此判定结束，只等“完成”按钮出现
  if ($h -eq [IntPtr]::Zero) { continue }
  $btn = [Dlg]::FindChildByTextPrefix($h, $labelFinish)
  if ($btn -ne [IntPtr]::Zero) { $finished = $true; break }
}
Write-Host "finish page reached: $finished"
if ($finished) {
  $h = Get-InstallerWindow $proc.Id
  $btn = [Dlg]::FindChildByTextPrefix($h, $labelFinish)
  if ($btn -ne [IntPtr]::Zero) {
    [void][Dlg]::SendMessage($btn, $WM_LBUTTONDOWN, [IntPtr]::Zero, [IntPtr]::Zero)
    [void][Dlg]::SendMessage($btn, $WM_LBUTTONUP, [IntPtr]::Zero, [IntPtr]::Zero)
    Write-Host 'clicked finish'
  }
  Start-Sleep -Seconds 3
}
$still = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
if ($still) { & taskkill.exe /PID $proc.Id /T /F | Out-Null; Write-Host 'forced close' }
Write-Host 'drive done'
