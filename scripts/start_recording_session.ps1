<#
.SYNOPSIS
    Zero-hardcoding session launcher that:
      1. Bootstraps OBS Studio profile/scenes via configure_studio.py if not yet configured on this machine
      2. Dynamically locates obs64.exe across standard install paths or PATH
      3. Starts OBS Studio in recording mode + starts the 10Hz Window/Cursor/Marker Telemetry Sidecar
#>
param(
    [string]$ProfileName = "ThirdWaveCircuit",
    [string]$Scene = "",
    [string]$OutputDir = (Join-Path $HOME "Videos\ThirdWaveCircuit\00_Inbox_Raw")
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bootstrapScript = Join-Path $scriptDir "configure_studio.py"

$obsProfileDir = Join-Path $env:APPDATA "obs-studio\basic\profiles\$ProfileName"
if ((-not (Test-Path $obsProfileDir)) -and (Test-Path $bootstrapScript)) {
    Write-Host "Bootstrapping OBS Studio configuration for this machine..." -ForegroundColor Yellow
    python $bootstrapScript --profile-name $ProfileName --output-dir $OutputDir
}

# Dynamically locate OBS Studio executable
$candidatePaths = @(
    (Get-Command "obs64.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Join-Path $env:ProgramFiles "obs-studio\bin\64bit\obs64.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "obs-studio\bin\64bit\obs64.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\obs-studio\bin\64bit\obs64.exe")
) | Where-Object { $_ -and (Test-Path $_) }

$obsExe = $candidatePaths | Select-Object -First 1
if (-not $obsExe) {
    $cachedInstaller = Get-ChildItem "$env:LOCALAPPDATA\Temp\WinGet" -Recurse -Filter "*OBS*Installer*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cachedInstaller) {
        Write-Warning "OBS Studio not installed yet. Launching cached installer: $($cachedInstaller.FullName)"
        Start-Process -FilePath $cachedInstaller.FullName -Wait
        $obsExe = Join-Path $env:ProgramFiles "obs-studio\bin\64bit\obs64.exe"
    } else {
        Write-Error "OBS Studio not found. Install it via: winget install OBSProject.OBSStudio"
        exit 1
    }
}

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$telemetryOut = Join-Path $OutputDir "session_${ts}_telemetry.jsonl"
$obsDir = Split-Path -Parent $obsExe

$obsArgs = @(
    "--profile", $ProfileName,
    "--collection", $ProfileName,
    "--startrecording"
)
if ($Scene) {
    $obsArgs += @("--scene", "`"$Scene`"")
}

Write-Host "Starting OBS Studio (Profile: $ProfileName)..." -ForegroundColor Cyan
Start-Process -FilePath $obsExe -WorkingDirectory $obsDir -ArgumentList $obsArgs

Write-Host "Starting Window/Cursor/Hotkey Telemetry Sidecar -> $telemetryOut" -ForegroundColor Green
python (Join-Path $scriptDir "track_context.py") --out $telemetryOut
