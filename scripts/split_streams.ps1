<#
.SYNOPSIS
    Splits a Double-Wide (3840x1080) synchronized OBS recording into 4 independent,
    frame-locked streams for downstream avatar generation, AI interpolation, or video editing:
      1. *_screen.mp4   (Left 1920x1080 - Clean Screen Capture)
      2. *_camera.mp4   (Right 1920x1080 - Clean Raw Webcam / Face Capture)
      3. *_voice.wav    (Audio Track 2 - Isolated Microphone)
      4. *_desktop.wav  (Audio Track 3 - Isolated System Audio)
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$InputFile,

    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutputDir) {
    $OutputDir = Split-Path -Parent $InputFile
}
$base = [System.IO.Path]::GetFileNameWithoutExtension($InputFile)

$screenOut  = Join-Path $OutputDir "${base}_screen.mp4"
$cameraOut  = Join-Path $OutputDir "${base}_camera.mp4"
$voiceOut   = Join-Path $OutputDir "${base}_voice.wav"
$desktopOut = Join-Path $OutputDir "${base}_desktop.wav"

Write-Host "1/4 Extracting Left 1920x1080 -> $screenOut ..."
ffmpeg -y -i $InputFile -filter:v "crop=1920:1080:0:0" -c:v h264_nvenc -cq 18 -preset p5 -map 0:a:0 -c:a aac -b:a 192k $screenOut

Write-Host "2/4 Extracting Right 1920x1080 (Raw Camera) -> $cameraOut ..."
ffmpeg -y -i $InputFile -filter:v "crop=1920:1080:1920:0" -c:v h264_nvenc -cq 18 -preset p5 -map 0:a:1 -c:a aac -b:a 192k $cameraOut

Write-Host "3/4 Extracting Isolated Voice (Track 2) -> $voiceOut ..."
ffmpeg -y -i $InputFile -map 0:a:1 -c:a pcm_s16le $voiceOut

Write-Host "4/4 Extracting Isolated Desktop Audio (Track 3) -> $desktopOut ..."
ffmpeg -y -i $InputFile -map 0:a:2 -c:a pcm_s16le $desktopOut

Write-Host "All 4 frame-locked streams extracted successfully!" -ForegroundColor Green
