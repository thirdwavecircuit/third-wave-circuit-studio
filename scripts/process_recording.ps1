<#
.SYNOPSIS
    Helper script for Third Wave Circuit recordings:
    - Remuxes crash-safe .mkv recordings to .mp4 (instant, zero quality loss)
    - Generates fast timelapses (e.g. 10x or 20x speed) from long drawing/coding sessions
    - Extracts isolated audio tracks (Track 1: Master, Track 2: Mic Only, Track 3: Desktop Only)
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$InputFile,

    [ValidateSet("remux", "timelapse", "extract-mic")]
    [string]$Action = "remux",

    [int]$SpeedMultiplier = 10
)

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $InputFile
$base = [System.IO.Path]::GetFileNameWithoutExtension($InputFile)

switch ($Action) {
    "remux" {
        $out = Join-Path $dir "$base.mp4"
        Write-Host "Remuxing $InputFile -> $out (lossless copy)..."
        ffmpeg -y -i $InputFile -map 0 -c copy $out
        Write-Host "Done: $out"
    }
    "timelapse" {
        $out = Join-Path $dir "${base}_timelapse_${SpeedMultiplier}x.mp4"
        $pts = [math]::Round(1.0 / $SpeedMultiplier, 4)
        Write-Host "Creating ${SpeedMultiplier}x video timelapse -> $out..."
        ffmpeg -y -i $InputFile -an -filter:v "setpts=${pts}*PTS" -c:v h264_nvenc -cq 20 -preset p5 $out
        Write-Host "Done: $out"
    }
    "extract-mic" {
        $out = Join-Path $dir "${base}_mic_only.wav"
        Write-Host "Extracting isolated Mic track (Track 2) -> $out..."
        ffmpeg -y -i $InputFile -map 0:a:1 -c:a pcm_s16le $out
        Write-Host "Done: $out"
    }
}
