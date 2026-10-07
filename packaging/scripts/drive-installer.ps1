<#
.SYNOPSIS
  Drive the SugarAgent installer through UI Automation: advance pages, optionally uncheck the
  desktop-shortcut checkbox, capture the shortcut-options page, and finish the install.
  NOTE: saved with a UTF-8 BOM because Windows PowerShell 5.1 would otherwise read the Chinese
  UI literals below as ANSI and fail to parse.
#>
param(
  [Parameter(Mandatory)][string]$Installer,
  [Parameter(Mandatory)][string]$ShotPath,
  [switch]$UncheckDesktop,
  [int]$WaitSeconds = 30
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class SugarShot {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
}
"@

function Get-WindowHandle($procId) {
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if ($p -and $p.MainWindowHandle -ne 0) { return $p.MainWindowHandle }
  return [IntPtr]::Zero
}
function Get-Root($hwnd) { return [System.Windows.Automation.AutomationElement]::FromHandle($hwnd) }
function Find-Prefix($root, $prefix) {
  # 只在按钮里找，避免命中同名静态文本
  $cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button)
  $buttons = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
  foreach ($el in $buttons) {
    $name = $el.Current.Name
    if ($name -and $name.StartsWith($prefix)) { return $el }
  }
  return $null
}
function Find-CheckBox($root, $name) {
  $typeCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::CheckBox)
  $nameCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::NameProperty, $name)
  $cond = New-Object System.Windows.Automation.AndCondition($typeCond, $nameCond)
  return $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
}
function Invoke-Element($el) {
  try {
    $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  } catch {
    $el.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern).DoDefaultAction()
  }
}
function Capture($hwnd, $path) {
  $rect = New-Object 'SugarShot+RECT'
  [void][SugarShot]::GetWindowRect($hwnd, [ref]$rect)
  $w = $rect.Right - $rect.Left; $h = $rect.Bottom - $rect.Top
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  [void][SugarShot]::PrintWindow($hwnd, $hdc, 2)
  $g.ReleaseHdc($hdc)
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  Write-Host "captured $w x $h -> $path"
}

$proc = Start-Process -FilePath $Installer -PassThru
Write-Host "installer pid=$($proc.Id)"
$hwnd = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline -and $hwnd -eq [IntPtr]::Zero) {
  Start-Sleep -Milliseconds 500
  $hwnd = Get-WindowHandle $proc.Id
}
if ($hwnd -eq [IntPtr]::Zero) { Write-Host 'no installer window'; exit 1 }
Start-Sleep -Seconds 1

$next = Find-Prefix (Get-Root $hwnd) '下一步'
if (-not $next) { Write-Host 'next button not found'; exit 1 }
Invoke-Element $next; Write-Host 'clicked next'
Start-Sleep -Seconds 2

$hwnd = Get-WindowHandle $proc.Id
$root = Get-Root $hwnd
Capture $hwnd $ShotPath
$desktopBox = Find-CheckBox $root '创建桌面快捷方式'
$startBox = Find-CheckBox $root '在开始菜单中创建快捷方式'
Write-Host "desktop checkbox found: $($desktopBox -ne $null); start-menu checkbox found: $($startBox -ne $null)"
if ($UncheckDesktop -and $desktopBox) {
  $toggle = $desktopBox.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
  $toggle.Toggle()
  Write-Host "desktop checkbox now: $($toggle.Current.ToggleState)"
}

$install = Find-Prefix (Get-Root (Get-WindowHandle $proc.Id)) '安装'
if (-not $install) { Write-Host 'install button not found'; exit 1 }
Invoke-Element $install; Write-Host 'clicked install'

$done = $false
$deadline = (Get-Date).AddMinutes(5)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
  $r = Get-Root (Get-WindowHandle $proc.Id)
  if ($r -and (Find-Prefix $r '正在完成')) { $done = $true; break }
}
Write-Host "finish page reached: $done"

if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
  $r = Get-Root (Get-WindowHandle $proc.Id)
  $close = Find-Prefix $r '完成'
  if ($close) { Invoke-Element $close; Write-Host 'clicked finish' }
  Start-Sleep -Seconds 3
}
if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
  & taskkill.exe /PID $proc.Id /T /F | Out-Null
  Write-Host 'forced close'
}
Write-Host 'drive done'
