#requires -Version 5.1
<#
.SYNOPSIS
    Opens the SugarAgent WebUI in the default browser.
.DESCRIPTION
    Registered as the handler for the sugaragent:// URL protocol. Windows
    invokes this script when the user clicks a SugarAgent toast notification,
    which opens (or re-opens) the frontend page in the default browser.
#>

$ErrorActionPreference = "Stop"

$WebUiUrl = "http://127.0.0.1:8192/"

try {
    Start-Process -FilePath $WebUiUrl
    exit 0
} catch {
    try {
        cmd.exe /c start "" "$WebUiUrl"
        exit 0
    } catch {
        [Console]::Error.WriteLine("Unable to open SugarAgent WebUI: $($_.Exception.Message)")
        exit 1
    }
}
