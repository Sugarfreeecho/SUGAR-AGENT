<#
.SYNOPSIS  Dump the UI Automation tree of the SugarAgent installer window (diagnostic, ASCII-only). #>
param(
  [Parameter(Mandatory)][string]$Installer,
  [int]$WaitSeconds = 30
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes

$proc = Start-Process -FilePath $Installer -PassThru
Write-Host "pid=$($proc.Id)"
$hwnd = [IntPtr]::Zero
$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline -and $hwnd -eq [IntPtr]::Zero) {
  Start-Sleep -Milliseconds 500
  $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
  if ($p -and $p.MainWindowHandle -ne 0) { $hwnd = $p.MainWindowHandle }
}
if ($hwnd -eq [IntPtr]::Zero) { Write-Host 'no window'; exit 1 }
Start-Sleep -Seconds 2

$root = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
Write-Host "root type=$($root.Current.ControlType.ProgrammaticName) name='$($root.Current.Name)'"
$all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
Write-Host "descendants: $($all.Count)"
foreach ($el in $all) {
  $c = $el.Current
  if ($c.ControlType -eq [System.Windows.Automation.ControlType]::Button -or
      $c.ControlType -eq [System.Windows.Automation.ControlType]::CheckBox -or
      $c.ControlType -eq [System.Windows.Automation.ControlType]::RadioButton) {
    Write-Host ("  {0,-10} name='{1}'" -f $c.ControlType.ProgrammaticName.Replace('ControlType.',''), $c.Name)
  }
}
& taskkill.exe /PID $proc.Id /T /F | Out-Null
