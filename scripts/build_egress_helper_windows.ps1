param([switch]$InstallAcl, [string[]]$WorkDir)
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
    if (-not $WorkDir) {
        $PathsJson = & (Join-Path $Root 'python\python.exe') (Join-Path $Root 'app\workspace_paths.py') --project-root $Root
        if ($LASTEXITCODE -ne 0) { throw 'Failed to resolve configured workspace.' }
        $WorkDir = @([string]($PathsJson | ConvertFrom-Json).work_dir)
    }
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
    foreach ($TargetWorkDir in $WorkDir) {
        $ResolvedWorkDir = (Resolve-Path -LiteralPath $TargetWorkDir).Path
        $TraverseDir = Split-Path -Parent $ResolvedWorkDir
        while ($TraverseDir -and (Split-Path -Parent $TraverseDir)) {
            & icacls.exe $TraverseDir /grant ('*' + $Sid + ':(RX)') /Q | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Failed to grant AppContainer traverse access to $TraverseDir" }
            $TraverseDir = Split-Path -Parent $TraverseDir
        }
        & icacls.exe $ResolvedWorkDir /grant:r ('*' + $Sid + ':(OI)(CI)(M)') /T /C /Q | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to grant the AppContainer access to $ResolvedWorkDir" }
    }
}
Write-Host "Built: $Output"
Write-Host "Health: $($Health.enforcement) / $($Health.backend)"
