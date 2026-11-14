<#
.SYNOPSIS
    Mirrors completed local recordings and project assets from local SSD to a shared network drive / NAS
    using multi-threaded robocopy (safe against network drops, resumes interrupted transfers).
#>
param(
    [string]$LocalRoot = "$env:USERPROFILE\Videos\ThirdWaveCircuit",
    [Parameter(Mandatory=$true)]
    [string]$SharedPath
)

$ErrorActionPreference = "Stop"
Write-Host "Syncing $LocalRoot -> $SharedPath ..."

# Multi-threaded (/MT:8), restartable (/Z), exclude incomplete temp files
robocopy $LocalRoot $SharedPath /E /Z /MT:8 /R:3 /W:5 /NP
if ($LASTEXITCODE -lt 8) {
    Write-Host "Sync complete!" -ForegroundColor Green
    exit 0
} else {
    Write-Error "Robocopy reported errors (Exit code: $LASTEXITCODE)"
    exit $LASTEXITCODE
}
