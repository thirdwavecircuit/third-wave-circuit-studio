#!/usr/bin/env python3
"""
Declarative Post-Processing Compositor & Edit Plan Renderer (`render_roughcut.py`)

Reads a user-reviewed `*_edit_plan.yaml` file (plus `*_screen.mp4` and optional `*_camera.mp4` / AI avatar video)
and renders the final composed video according to your segment settings:
  - `action: keep`       -> Keeps spoken segment at 1x with -14 LUFS loudness normalization
  - `action: timelapse`  -> Speed-ramps silent coding/drawing stretches (e.g. 8x-15x)
  - `action: cut`        -> Drops the segment completely
  - `view_mode: full_screen | active_window` -> Uses telemetry bounding box (`dominant_window_rect`) to crop to active window
  - `show_avatar` / `avatar_overlay` -> Layers the offline-generated AI avatar or camera PiP on top of the screen
"""

import argparse
import os
import shutil
import subprocess
import tempfile
import yaml


def parse_time_sec(t_str: str) -> float:
    parts = [float(p) for p in str(t_str).split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def detect_ffmpeg_video_encoder() -> list:
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


def compute_overlay_xy(position: str, margin: int = 32) -> tuple:
    pos = (position or "bottom-right").lower()
    if pos == "bottom-left":
        return f"{margin}", f"main_h-overlay_h-{margin}"
    elif pos == "top-right":
        return f"main_w-overlay_w-{margin}", f"{margin}"
    elif pos == "top-left":
        return f"{margin}", f"{margin}"
    return f"main_w-overlay_w-{margin}", f"main_h-overlay_h-{margin}"


def build_crop_filter(rect: dict, src_w: int = 1920, src_h: int = 1080) -> str:
    if not rect:
        return ""
    x = max(0, min(src_w - 320, int(rect.get("x", 0)) % src_w))
    y = max(0, min(src_h - 240, int(rect.get("y", 0)) % src_h))
    w = max(320, min(src_w - x, int(rect.get("w", src_w))))
    h = max(240, min(src_h - y, int(rect.get("h", src_h))))
    # Ensure even dimensions for YUV420p encoding
    w -= w % 2
    h -= h % 2
    return f"crop={w}:{h}:{x}:{y}"


def render_plan(
    plan_path: str,
    screen_video: str,
    output_video: str,
    avatar_video: str = None,
    upscale_1440p: bool = False,
):
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = yaml.safe_load(f)

    segments = [s for s in plan.get("segments", []) if s.get("action") != "cut"]
    if not segments:
        print("No segments marked to keep/timelapse.")
        return

    temp_dir = tempfile.mkdtemp(prefix="twc_render_")
    part_files = []

    target_w, target_h = (2560, 1440) if upscale_1440p else (1920, 1080)
    v_enc = detect_ffmpeg_video_encoder()

    for idx, seg in enumerate(segments):
        start_sec = parse_time_sec(seg["start"])
        dur_sec = float(seg["duration_sec"])
        if dur_sec <= 0.2:
            continue

        speed = float(seg.get("speed", 1.0))
        part_out = os.path.join(temp_dir, f"part_{idx:04d}.mp4")

        v_filters = []
        if seg.get("view_mode") == "active_window" and seg.get("dominant_window_rect"):
            crop_f = build_crop_filter(seg["dominant_window_rect"])
            if crop_f:
                v_filters.append(crop_f)

        if speed != 1.0:
            v_filters.append(f"setpts={round(1.0 / speed, 5)}*PTS")
        v_filters.append(f"scale={target_w}:{target_h}:flags=lanczos")

        overlay_cfg = seg.get("avatar_overlay") or {}
        use_avatar = bool(
            avatar_video
            and os.path.exists(avatar_video)
            and seg.get("show_avatar", overlay_cfg.get("enabled", False))
        )

        is_timelapse = seg.get("action") == "timelapse" or speed > 2.0

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-t", str(dur_sec),
            "-i", screen_video,
        ]

        if use_avatar:
            cmd += ["-ss", str(start_sec), "-t", str(dur_sec), "-i", avatar_video]

        if is_timelapse:
            cmd += [
                "-f", "lavfi",
                "-t", str(max(0.1, round(dur_sec / speed, 2))),
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]

        if use_avatar:
            scale_ratio = float(overlay_cfg.get("scale", 0.28))
            pip_w = int(target_w * scale_ratio)
            pip_w -= pip_w % 2
            ox, oy = compute_overlay_xy(overlay_cfg.get("position", "bottom-right"))
            base_chain = ",".join(v_filters)
            pip_pts = f"setpts={round(1.0 / speed, 5)}*PTS," if speed != 1.0 else ""
            filter_complex = (
                f"[0:v]{base_chain}[bg];"
                f"[1:v]{pip_pts}scale={pip_w}:-2:flags=lanczos[pip];"
                f"[bg][pip]overlay={ox}:{oy}:shortest=1[vout]"
            )
            cmd += ["-filter_complex", filter_complex, "-map", "[vout]"]
        else:
            cmd += ["-filter:v", ",".join(v_filters), "-map", "0:v:0"]

        cmd += v_enc

        if is_timelapse:
            anull_idx = 2 if use_avatar else 1
            cmd += [
                "-map", f"{anull_idx}:a:0",
                "-c:a", "aac", "-b:a", "192k", "-shortest",
            ]
        else:
            cmd += [
                "-map", "0:a:0",
                "-filter:a", "highpass=f=80,loudnorm=I=-14:TP=-1.0:LRA=11",
                "-c:a", "aac", "-b:a", "192k",
            ]

        cmd.append(part_out)
        print(f"Rendering segment #{seg['id']} ({seg['start']} -> {seg['end']}, {seg['action']} @ {speed}x)...")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        part_files.append(part_out)

    concat_list = os.path.join(temp_dir, "concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in part_files:
            safe_p = p.replace("\\", "/")
            f.write(f"file '{safe_p}'\n")

    print(f"Concatenating {len(part_files)} rendered segments -> {output_video}...")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", output_video],
        check=True,
    )
    print(f"[OK] Finished rendering rough cut: {output_video}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render an edited *_edit_plan.yaml into a composed rough-cut MP4")
    parser.add_argument("--plan", required=True, help="Path to *_edit_plan.yaml")
    parser.add_argument("--screen", required=True, help="Path to *_screen.mp4")
    parser.add_argument("--avatar", help="Optional path to *_camera.mp4 or offline-generated AI avatar MP4 for PiP overlay")
    parser.add_argument("--out", required=True, help="Output MP4 path")
    parser.add_argument("--upscale-1440p", action="store_true", help="Upscale to 2560x1440 to force YouTube VP09 codec")
    args = parser.parse_args()
    render_plan(args.plan, args.screen, args.out, avatar_video=args.avatar, upscale_1440p=args.upscale_1440p)
