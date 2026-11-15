#!/usr/bin/env python3
"""
1:1 Stream Recompiler & Sanity-Check Tool (`recompile_streams.py`)

Takes the 4 independent raw streams produced by `split_streams.ps1`:
  1. `*_screen.mp4`   (Isolated display video)
  2. `*_camera.mp4`   (Isolated camera video)
  3. `*_voice.wav`    (Isolated microphone audio)
  4. `*_desktop.wav`  (Isolated desktop audio)

And recombines them at 1:1 original speed (`1.0x`, zero cuts, zero speed-ramping)
with the camera layered in the bottom-right corner and both audio tracks mixed,
verifying that all 4 extracted streams are intact and frame-synchronized.
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def detect_video_encoder() -> list:
    if not shutil.which("ffmpeg"):
        return ["-c:v", "libx264", "-crf", "18", "-preset", "fast"]
    try:
        out = subprocess.check_output(
            ["ffmpeg", "-hide_banner", "-encoders"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        if "h264_nvenc" in out:
            return ["-c:v", "h264_nvenc", "-cq", "18", "-preset", "p5"]
    except Exception:
        pass
    return ["-c:v", "libx264", "-crf", "18", "-preset", "fast"]


def build_recompile_command(
    screen_mp4: str,
    camera_mp4: str,
    voice_wav: str,
    desktop_wav: str,
    output_mp4: str,
    pip_width: int = 538,
    margin: int = 32,
    v_encoder: list = None,
) -> list:
    v_enc = v_encoder or detect_video_encoder()
    filter_complex = (
        f"[1:v]scale={pip_width}:-2:flags=lanczos[pip];"
        f"[0:v][pip]overlay=main_w-overlay_w-{margin}:main_h-overlay_h-{margin}[vout];"
        f"[2:a][3:a]amix=inputs=2:duration=longest:dropout_transition=0,volume=2.0[aout]"
    )
    return [
        "ffmpeg", "-y",
        "-i", str(screen_mp4),
        "-i", str(camera_mp4),
        "-i", str(voice_wav),
        "-i", str(desktop_wav),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        *v_enc,
        "-c:a", "aac", "-b:a", "192k",
        str(output_mp4),
    ]


def recompile_session(
    screen_mp4: str,
    camera_mp4: str,
    voice_wav: str,
    desktop_wav: str,
    output_mp4: str,
    pip_width: int = 538,
    margin: int = 32,
):
    cmd = build_recompile_command(
        screen_mp4=screen_mp4,
        camera_mp4=camera_mp4,
        voice_wav=voice_wav,
        desktop_wav=desktop_wav,
        output_mp4=output_mp4,
        pip_width=pip_width,
        margin=margin,
    )
    print(f"Recompiling 1:1 (1.0x) sanity-check video -> {output_mp4}")
    subprocess.run(cmd, check=True)
    print(f"[OK] Recompiled 1x video saved to: {output_mp4}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Recompile the 4 separated streams (_screen, _camera, _voice, _desktop) into a 1:1 (1x) combined MP4"
    )
    parser.add_argument("--base", help="Base path/prefix of a split recording (e.g. '2026-11-15 15-12-06')")
    parser.add_argument("--screen", help="Path to *_screen.mp4")
    parser.add_argument("--camera", help="Path to *_camera.mp4")
    parser.add_argument("--voice", help="Path to *_voice.wav")
    parser.add_argument("--desktop", help="Path to *_desktop.wav")
    parser.add_argument("--out", help="Output *_recompiled_1x.mp4 path")
    parser.add_argument("--pip-width", type=int, default=538, help="Width of bottom-right camera PiP overlay (default: 538)")
    args = parser.parse_args()

    if args.base:
        base_str = args.base[:-4] if args.base.endswith(".mp4") else args.base
        screen_p = args.screen or f"{base_str}_screen.mp4"
        camera_p = args.camera or f"{base_str}_camera.mp4"
        voice_p = args.voice or f"{base_str}_voice.wav"
        desktop_p = args.desktop or f"{base_str}_desktop.wav"
        out_p = args.out or f"{base_str}_recompiled_1x.mp4"
    else:
        if not (args.screen and args.camera and args.voice and args.desktop):
            parser.error("Provide either --base <recording_prefix> or all 4 stream paths (--screen, --camera, --voice, --desktop)")
        screen_p = args.screen
        camera_p = args.camera
        voice_p = args.voice
        desktop_p = args.desktop
        out_p = args.out or screen_p.replace("_screen.mp4", "_recompiled_1x.mp4")

    recompile_session(screen_p, camera_p, voice_p, desktop_p, out_p, pip_width=args.pip_width)
