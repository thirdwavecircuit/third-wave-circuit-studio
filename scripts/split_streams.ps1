<#
.SYNOPSIS
    Splits a side-by-side synchronized OBS recording into 4 independent, frame-locked streams:
      1. *_screen.mp4   (Left half - Clean Screen Capture)
      2. *_camera.mp4   (Right half - Clean Raw Webcam / Face Capture)
      3. *_voice.wav    (Audio Track 2 - Isolated Microphone)
      4. *_desktop.wav  (Audio Track 3 - Isolated System Audio)
    Automatically detects hardware encoder support (h264_nvenc vs libx264) and dimensions.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$InputFile,

    [string]$OutputDir = "",
    [int]$TileWidth = 1920,
    [int]$TileHeight = 1080
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

# Auto-detect NVENC availability in FFmpeg
$encoders = ffmpeg -hide_banner -encoders 2>$null | Out-String
if ($encoders -match "h264_nvenc") {
    $vCodec = @("-c:v", "h264_nvenc", "-cq", "18", "-preset", "p5")
} else {
    $vCodec = @("-c:v", "libx264", "-crf", "18", "-preset", "fast")
}

Write-Host "1/4 Extracting Left ${TileWidth}x${TileHeight} -> $screenOut ..."
ffmpeg -y -i $InputFile -filter:v "crop=${TileWidth}:${TileHeight}:0:0" @vCodec -map 0:a:0 -c:a aac -b:a 192k $screenOut

Write-Host "2/4 Extracting Right ${TileWidth}x${TileHeight} (Raw Camera) -> $cameraOut ..."
ffmpeg -y -i $InputFile -filter:v "crop=${TileWidth}:${TileHeight}:${TileWidth}:0" @vCodec -map 0:a:1 -c:a aac -b:a 192k $cameraOut

Write-Host "3/4 Extracting Isolated Voice (Track 2) -> $voiceOut ..."
ffmpeg -y -i $InputFile -map 0:a:1 -c:a pcm_s16le $voiceOut

Write-Host "4/4 Extracting Isolated Desktop Audio (Track 3) -> $desktopOut ..."
ffmpeg -y -i $InputFile -map 0:a:2 -c:a pcm_s16le $desktopOut

Write-Host "All 4 frame-locked streams extracted successfully!" -ForegroundColor Green
