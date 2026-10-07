<#
.SYNOPSIS  Drive the SugarAgent installer via MSAA (IAccessible), which classic NSIS dialogs do expose.
.DESCRIPTION  Advances the wizard, toggles the desktop-shortcut checkbox, captures the page and
              finishes the install. Saved with UTF-8 BOM for Windows PowerShell 5.1.
#>
param(
  [Parameter(Mandatory)][string]$Installer,
  [Parameter(Mandatory)][string]$ShotPath,
  [switch]$UncheckDesktop,
  [int]$WaitSeconds = 40
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName Accessibility, System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class Msaa {
  [DllImport("oleacc.dll")] public static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint id, ref Guid iid, [MarshalAs(UnmanagedType.Interface)] out object acc);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@

function Get-Acc($hwnd) {
  $iid = [Guid]'618736E0-3C3D-11CF-810C-00AA00389B71'   # IID_IAccessible
  $obj = $null
  $objIdClient = [uint32]4294967292   # OBJID_CLIENT (0xFFFFFFFC)
  $hr = [Msaa]::AccessibleObjectFromWindow($hwnd, $objIdClient, [ref]$iid, [ref]$obj)
  if ($hr -ne 0 -or $null -eq $obj) { throw "AccessibleObjectFromWindow failed hr=$hr" }
  return $obj
}
function Walk-Children($acc, $depth, [ref]$found, $prefix, $roleFilter) {
  if ($depth -gt 4) { return }
  $count = 0
  try { $count = $acc.accChildCount } catch { return }
  for ($i = 1; $i -le $count; $i++) {
    $child = $null
    try { $child = $acc.accChild($i) } catch { continue }
    if ($null -eq $child) { continue }
    $name = ''
    try { $name = [string]$acc.get_accName($i) } catch { $name = '' }
    $role = 0
    try { $role = [int]$acc.get_accRole($i) } catch { $role = 0 }
    if ($name -and $prefix -and $name.StartsWith($prefix) -and ($roleFilter -eq 0 -or $role -eq $roleFilter)) {
      $found.Value = @{ Parent = $acc; Index = $i; Name = $name; Role = $role }
      return
    }
    Walk-Children $child ($depth + 1) $found $prefix $roleFilter
    if ($found.Value) { return }
  }
}
function Find-Acc([IntPtr]$hwnd, $prefix, $roleFilter = 0) {
  $acc = Get-Acc $hwnd
  $found = [ref]$null
  Walk-Children $acc 0 $found $prefix $roleFilter
  return $found.Value
}
function Invoke-Acc($entry) {
  $entry.Parent.accDoDefaultAction($entry.Index)
}

$proc = Start-Process -FilePath $Installer -PassThru
Write-Host "installer pid=$($proc.Id)"
function Current-Hwnd {
  $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
  if ($p -and $p.MainWindowHandle -ne 0) { return $p.MainWindowHandle }
  return [IntPtr]::Zero
}
$hwnd = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline -and $hwnd -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 500; $hwnd = Current-Hwnd }
if ($hwnd -eq [IntPtr]::Zero) { Write-Host 'no window'; exit 1 }
Start-Sleep -Seconds 2
[void][Msaa]::SetForegroundWindow($hwnd)

# 第 1 页（选定安装位置）→ 下一步
$next = Find-Acc $hwnd '下一步'
if (-not $next) { Write-Host 'button 下一步 not found'; & taskkill.exe /PID $proc.Id /T /F | Out-Null; exit 1 }
Invoke-Acc $next
Write-Host 'clicked next'
Start-Sleep -Seconds 2

# 第 2 页：自定义“快捷方式选项”页
$hwnd = Current-Hwnd
$shot = @{}
$rect = New-Object 'Msaa+RECT'
[void][Msaa]::GetWindowRect($hwnd, [ref]$rect)
$bmp = New-Object System.Drawing.Bitmap ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc(); [void][Msaa]::PrintWindow($hwnd, $hdc, 2); $g.ReleaseHdc($hdc)
$bmp.Save($ShotPath, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
Write-Host "captured -> $ShotPath"

$desktop = Find-Acc $hwnd '创建桌面快捷方式'
$startMenu = Find-Acc $hwnd '在开始菜单中创建快捷方式'
Write-Host "desktop checkbox found: $($desktop -ne $null); start-menu checkbox found: $($startMenu -ne $null)"
if ($UncheckDesktop -and $desktop) {
  Invoke-Acc $desktop
  Start-Sleep -Milliseconds 500
  $state = 0
  try { $state = [int]$desktop.Parent.get_accState($desktop.Index) } catch { }
  Write-Host ("desktop checkbox state after toggle: 0x{0:X} (0x10=checked)" -f $state)
}

# 安装
$install = Find-Acc (Current-Hwnd) '安装'
if (-not $install) { Write-Host 'button 安装 not found'; & taskkill.exe /PID $proc.Id /T /F | Out-Null; exit 1 }
Invoke-Acc $install
Write-Host 'clicked install'

$done = $false
$deadline = (Get-Date).AddMinutes(5)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
  $h = Current-Hwnd
  if ($h -ne [IntPtr]::Zero -and (Find-Acc $h '完成')) { $done = $true; break }
}
Write-Host "finish seen: $done"
if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
  $fin = Find-Acc (Current-Hwnd) '完成'
  if ($fin) { Invoke-Acc $fin; Start-Sleep -Seconds 3 }
}
if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) { & taskkill.exe /PID $proc.Id /T /F | Out-Null; Write-Host 'forced close' }
Write-Host 'drive done'
