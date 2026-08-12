param([switch]$InstallAcl)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $Root 'app\native\windows\SugarAgentEgressHelper.cs'
$Output = Join-Path $Root 'app\native\sugaragent-egress-helper.exe'
$Compiler = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $Compiler)) { $Compiler = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe" }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Windows C# compiler is unavailable.' }
& $Compiler /nologo /optimize+ /target:exe "/out:$Output" /reference:System.Web.Extensions.dll $Source
if ($LASTEXITCODE -ne 0) { throw "Helper compilation failed with exit code $LASTEXITCODE" }
$Health = & $Output health --json | ConvertFrom-Json
if ($Health.enforcement -notin @('partial','strong')) { throw "Helper self-check failed: $($Health.reason)" }
if ($InstallAcl) {
    $Sid = [string]$Health.appcontainer_sid
    $Parent = Split-Path -Parent $Root
    while ($Parent -and (Split-Path -Parent $Parent)) {
        & icacls.exe $Parent /grant ('*' + $Sid + ':(RX)') /Q | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to grant AppContainer traverse access to $Parent" }
        $Next = Split-Path -Parent $Parent
        if ($Next -eq $Parent) { break }
        $Parent = $Next
    }
    & icacls.exe $Root /grant ('*' + $Sid + ':(OI)(CI)(RX)') /T /C /Q | Out-Null
    & icacls.exe (Join-Path $Root 'workspace') /grant:r ('*' + $Sid + ':(OI)(CI)(M)') /T /C /Q | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Failed to grant the AppContainer access to the workspace.' }
}
Write-Host "Built: $Output"
Write-Host "Health: $($Health.enforcement) / $($Health.backend)"
