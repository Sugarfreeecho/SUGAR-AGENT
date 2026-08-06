#requires -Version 5.1
<#
.SYNOPSIS
    Shows a Windows 10/11 system toast notification (Action Center) for SugarAgent.
.DESCRIPTION
    Used by app/desktop_notify.py after the last WebUI tab is closed.  The
    notification is delivered by Windows.UI.Notifications so it appears in the
    system notification center, not as a tray balloon.

    SugarAgent registers its own AUMID (HKCU\Software\Classes\AppUserModelId)
    so the toast is attributed to SugarAgent.  If that registration or delivery
    fails, the script falls back to an AUMID of an already installed app
    (PowerShell, Windows Terminal, ...) so the toast still shows.

    Clicking the toast (or its action button) opens the WebUI through the
    sugaragent:// URL protocol, whose handler is app/open_ui_from_notify.ps1.
#>

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptRoot

$Title = if ($env:SUGARAGENT_NOTIFY_TITLE) { $env:SUGARAGENT_NOTIFY_TITLE } else { "SugarAgent" }
$Message = if ($env:SUGARAGENT_NOTIFY_MESSAGE) {
    $env:SUGARAGENT_NOTIFY_MESSAGE
} else {
    "SugarAgent is running in the background; tasks will not be interrupted."
}

$SugarAgentAumid = "SugarAgent.MyAgent.UI"
$AumidRegistryPath = "HKCU:\Software\Classes\AppUserModelId\$SugarAgentAumid"
$TrayIconPath = Join-Path $Root "app\assets\sugar_tray.ico"

$OpenUiProtocol = "sugaragent"
$OpenUiProtocolRoot = "HKCU:\Software\Classes\$OpenUiProtocol"
$OpenUiScriptPath = Join-Path $Root "app\open_ui_from_notify.ps1"
$OpenUiLaunchUri = "sugaragent://open-ui"
$OpenUiCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$OpenUiScriptPath`""

# Fallback: the well-known AppID of Windows PowerShell.  Get-StartApps normally
# returns the real registered AppIDs, but keep a hardcoded one as a last resort.
$PowerShellAumidFallback = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

function Register-SugarAgentAumid {
    try {
        if (-not (Test-Path -LiteralPath $AumidRegistryPath)) {
            New-Item -Path $AumidRegistryPath -Force | Out-Null
        }
        New-ItemProperty -LiteralPath $AumidRegistryPath -Name "DisplayName" -Value "SugarAgent" -PropertyType String -Force | Out-Null
        if (Test-Path -LiteralPath $TrayIconPath) {
            New-ItemProperty -LiteralPath $AumidRegistryPath -Name "IconUri" -Value $TrayIconPath -PropertyType String -Force | Out-Null
        }
        return $true
    } catch {
        Write-Warning "Unable to register SugarAgent AUMID: $($_.Exception.Message)"
        return $false
    }
}

function Register-OpenUiProtocol {
    if (-not (Test-Path -LiteralPath $OpenUiScriptPath)) {
        Write-Warning "Missing UI opener script: $OpenUiScriptPath"
        return $false
    }
    try {
        New-Item -Path $OpenUiProtocolRoot -Force | Out-Null
        New-Item -Path "$OpenUiProtocolRoot\shell\open\command" -Force | Out-Null
        Set-ItemProperty -LiteralPath $OpenUiProtocolRoot -Name "(default)" -Value "URL:SugarAgent Protocol" -Force
        Set-ItemProperty -LiteralPath $OpenUiProtocolRoot -Name "URL Protocol" -Value "" -Force
        Set-ItemProperty -LiteralPath "$OpenUiProtocolRoot\shell\open\command" -Name "(default)" -Value $OpenUiCommand -Force
        return $true
    } catch {
        Write-Warning "Unable to register $OpenUiProtocol protocol: $($_.Exception.Message)"
        return $false
    }
}

function Get-AvailableAppIds {
    try {
        $apps = @(Get-StartApps -ErrorAction SilentlyContinue)
    } catch {
        $apps = @()
    }
    $preferredNames = @(
        "Windows PowerShell",
        "PowerShell",
        "Windows Terminal",
        "Terminal",
        "File Explorer",
        "Microsoft Edge",
        "Google Chrome"
    )
    $appIds = @()
    foreach ($name in $preferredNames) {
        $hit = $apps | Where-Object { $_.Name -like "*$name*" -and $_.AppID } | Select-Object -First 1
        if ($hit -and ($appIds -notcontains $hit.AppID)) {
            $appIds += $hit.AppID
        }
    }
    foreach ($app in $apps) {
        if ($app.AppID -and ($appIds -notcontains $app.AppID)) {
            $appIds += $app.AppID
        }
    }
    return $appIds
}

function New-SugarAgentToastXml {
    $safeTitle = [System.Security.SecurityElement]::Escape($Title)
    $safeMessage = [System.Security.SecurityElement]::Escape($Message)
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml(@"
<toast activationType="protocol" launch="$OpenUiLaunchUri">
  <visual>
    <binding template="ToastText02">
      <text id="1">$safeTitle</text>
      <text id="2">$safeMessage</text>
    </binding>
  </visual>
  <actions>
    <action activationType="protocol" arguments="$OpenUiLaunchUri" content="打开 SugarAgent"/>
  </actions>
</toast>
"@)
    return $xml
}

function Show-SugarAgentToast {
    param([string]$AppId)

    $xml = New-SugarAgentToastXml
    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppId).Show($toast)
}

try {
    # Load the WinRT types used by the Windows notification APIs.
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

    $null = Register-OpenUiProtocol

    $candidateAppIds = @()
    if (Register-SugarAgentAumid) {
        $candidateAppIds += $SugarAgentAumid
    }
    $candidateAppIds += Get-AvailableAppIds
    $candidateAppIds += $PowerShellAumidFallback

    foreach ($appId in ($candidateAppIds | Select-Object -Unique)) {
        try {
            Show-SugarAgentToast -AppId $appId
            exit 0
        } catch {
            Write-Warning "Toast failed with AppID '$appId': $($_.Exception.Message)"
        }
    }

    Write-Error "Unable to show SugarAgent toast through any registered AppID."
    exit 1
} catch {
    Write-Warning "Toast initialization failed: $($_.Exception.Message)"
    exit 1
}
