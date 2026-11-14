<#
.SYNOPSIS
    One-command launcher that starts BOTH:
      1. OBS Studio in the ThirdWaveCircuit profile & scene collection (with --startrecording)
      2. The synchronized 10Hz Window, Cursor & F9/F10 Marker Telemetry Logger (track_context.py)
#>
param(
    [ValidateSet(
        "ISO: Display 2 + Camera",
        "ISO: Display 1 + Camera",
        "ISO: Both Monitors (Display 1 + Display 2)"
    )]
    [string]$Scene = "ISO: Display 2 + Camera",

    [string]$OutputDir = "$env:USERPROFILE\Videos\ThirdWaveCircuit\00_Inbox_Raw"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$obsExe = "C:\Program Files\obs-studio\bin\64bit\obs64.exe"
if (-not (Test-Path $obsExe)) {
    Write-Error "OBS Studio not found at $obsExe. Run: winget install OBSProject.OBSStudio"
    exit 1
}

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$telemetryOut = Join-Path $OutputDir "session_${ts}_telemetry.jsonl"
$obsDir = Split-Path -Parent $obsExe

Write-Host "Starting OBS Studio (Profile: ThirdWaveCircuit, Scene: $Scene)..." -ForegroundColor Cyan
Start-Process -FilePath $obsExe -WorkingDirectory $obsDir -ArgumentList @(
    "--profile", "ThirdWaveCircuit",
    "--collection", "ThirdWaveCircuit",
    "--scene", "`"$Scene`"",
    "--startrecording"
)

Write-Host "Starting Window/Cursor/Hotkey Telemetry Sidecar -> $telemetryOut" -ForegroundColor Green
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $scriptDir "track_context.py") --out $telemetryOut
