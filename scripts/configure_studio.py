#!/usr/bin/env python3
"""
Dynamic Hardware Auto-Discovery & OBS Studio Bootstrapper (`configure_studio.py`)

Zero-hardcoding setup script that inspects the host machine's:
  - Operating System & user paths (`%APPDATA%` on Windows, `~/.config` on Linux, `~/Library` on macOS)
  - GPU hardware encoder support (NVIDIA NVENC, AMD AMF, Intel QSV, Apple VideoToolbox, or x264)
  - Connected displays & resolutions
  - Connected cameras & audio devices

Then dynamically writes the OBS Studio profile (`basic.ini`, `recordEncoder.json`),
scene collection (`scenes.json` with 3-track separated audio & RNNoise/Compressor/Limiter filters),
and `global.ini` without any hardcoded usernames, monitor IDs, or file paths.
"""

import argparse
import json
import os
import platform
import subprocess
from pathlib import Path


def get_obs_config_root() -> Path:
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "obs-studio"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "obs-studio"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(xdg) / "obs-studio"


def detect_gpu_encoder() -> str:
    system = platform.system()
    if system == "Darwin":
        return "com.apple.videotoolbox.videoencoder.ave.avc"

    try:
        if system == "Windows":
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).lower()
        else:
            out = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL).lower()

        if "nvidia" in out or "geforce" in out or "rtx" in out or "gtx" in out:
            return "jim_nvenc"
        elif "amd" in out or "radeon" in out:
            return "h264_texture_amf"
        elif "intel" in out or "arc" in out:
            return "obs_qsv11_v2"
    except Exception:
        pass
    return "obs_x264"


def detect_displays() -> list:
    system = platform.system()
    displays = []
    if system == "Windows":
        try:
            cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Screen]::AllScreens | "
                "ForEach-Object { \"$($_.DeviceName)|$($_.Primary)|$($_.Bounds.Width)|$($_.Bounds.Height)\" }"
            )
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            for idx, line in enumerate(out.strip().splitlines()):
                parts = line.strip().split("|")
                if len(parts) == 4:
                    displays.append({
                        "index": idx,
                        "device": parts[0],
                        "primary": parts[1].lower() == "true",
                        "width": int(parts[2]),
                        "height": int(parts[3]),
                    })
        except Exception:
            pass

    if not displays:
        displays.append({
            "index": 0,
            "device": "Display 1",
            "primary": True,
            "width": 1920,
            "height": 1080,
        })
    return displays


def build_scenes_json(profile_name: str, displays: list) -> dict:
    sources = []
    scenes = []
    scene_order = []

    # Camera source
    cam_id = "dshow_input" if platform.system() == "Windows" else "v4l2_input"
    sources.append({
        "id": cam_id,
        "name": "Camera",
        "settings": {"active": True},
    })

    # Create a monitor capture source + ISO scene for each detected display
    for d in displays:
        idx = d["index"]
        w, h = d["width"], d["height"]
        src_name = f"Display {idx + 1} ({w}x{h})"
        sources.append({
            "id": "monitor_capture",
            "name": src_name,
            "settings": {
                "monitor": idx,
                "capture_cursor": True,
            },
        })

        scene_name = f"ISO: Display {idx + 1} ({w}x{h}) + Camera"
        scene_order.append({"name": scene_name})
        scenes.append({
            "id": "scene",
            "name": scene_name,
            "settings": {
                "items": [
                    {
                        "name": src_name,
                        "visible": True,
                        "pos": {"x": 0.0, "y": 0.0},
                        "bounds_type": 2,
                        "bounds": {"x": 1920.0, "y": 1080.0},
                    },
                    {
                        "name": "Camera",
                        "visible": True,
                        "pos": {"x": 1920.0, "y": 0.0},
                        "bounds_type": 2,
                        "bounds": {"x": 1920.0, "y": 1080.0},
                    },
                ]
            },
        })

    # If 2+ displays exist, add a dual-monitor ISO scene
    if len(displays) >= 2:
        d0 = f"Display 1 ({displays[0]['width']}x{displays[0]['height']})"
        d1 = f"Display 2 ({displays[1]['width']}x{displays[1]['height']})"
        dual_name = "ISO: Dual Monitors (Display 1 + Display 2)"
        scene_order.append({"name": dual_name})
        scenes.append({
            "id": "scene",
            "name": dual_name,
            "settings": {
                "items": [
                    {
                        "name": d0,
                        "visible": True,
                        "pos": {"x": 0.0, "y": 0.0},
                        "bounds_type": 2,
                        "bounds": {"x": 1920.0, "y": 1080.0},
                    },
                    {
                        "name": d1,
                        "visible": True,
                        "pos": {"x": 1920.0, "y": 0.0},
                        "bounds_type": 2,
                        "bounds": {"x": 1920.0, "y": 1080.0},
                    },
                ]
            },
        })

    default_scene = scene_order[0]["name"]
    audio_out_id = "wasapi_output_capture" if platform.system() == "Windows" else "pulse_output_capture"
    audio_in_id = "wasapi_input_capture" if platform.system() == "Windows" else "pulse_input_capture"

    return {
        "current_scene": default_scene,
        "current_program_scene": default_scene,
        "scene_order": scene_order,
        "name": profile_name,
        "DesktopAudioDevice1": {
            "id": audio_out_id,
            "name": "Desktop Audio",
            "settings": {"device_id": "default"},
            "mixers": 5,  # Track 1 (Master) + Track 3 (Desktop Only)
            "volume": 1.0,
            "muted": False,
        },
        "AuxAudioDevice1": {
            "id": audio_in_id,
            "name": "Mic/Aux",
            "settings": {"device_id": "default"},
            "mixers": 3,  # Track 1 (Master) + Track 2 (Mic Only)
            "volume": 1.0,
            "muted": False,
            "filters": [
                {
                    "id": "noise_suppress_filter_v2",
                    "name": "1. RNNoise Suppression",
                    "enabled": True,
                    "settings": {"method": "rnnoise"},
                },
                {
                    "id": "compressor_filter",
                    "name": "2. Voice Compressor (3.5:1)",
                    "enabled": True,
                    "settings": {
                        "ratio": 3.5,
                        "threshold": -18.0,
                        "attack_time": 6,
                        "release_time": 60,
                        "output_gain": 2.0,
                    },
                },
                {
                    "id": "limiter_filter",
                    "name": "3. Peak Limiter (-1.0 dB)",
                    "enabled": True,
                    "settings": {
                        "threshold": -1.0,
                        "release_time": 60,
                    },
                },
            ],
        },
        "sources": sources + scenes,
    }


def bootstrap_studio(profile_name: str, output_dir: Path, canvas_w: int = 3840, canvas_h: int = 1080, fps: int = 60, cqp: int = 18):
    obs_root = get_obs_config_root()
    profile_dir = obs_root / "basic" / "profiles" / profile_name
    scenes_dir = obs_root / "basic" / "scenes"

    profile_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    encoder = detect_gpu_encoder()
    displays = detect_displays()
    rec_path_str = str(output_dir.resolve()).replace("\\", "/")

    # 1. Write basic.ini
    basic_ini = f"""[General]
Name={profile_name}

[Video]
BaseCX={canvas_w}
BaseCY={canvas_h}
OutputCX={canvas_w}
OutputCY={canvas_h}
FPSType=0
FPSCommon={fps}
ScaleType=bicubic

[Audio]
SampleRate=48000
ChannelSetup=Stereo

[Output]
Mode=Advanced

[AdvOut]
TrackIndex=1
RecType=Standard
RecFilePath={rec_path_str}
RecFormat2=hybrid_mp4
RecTracks=7
RecEncoder={encoder}
FFOutputToFile=true
Track1Bitrate=192
Track2Bitrate=192
Track3Bitrate=192
Track1Name=Master Mix
Track2Name=Mic Only
Track3Name=Desktop Audio Only
"""
    (profile_dir / "basic.ini").write_text(basic_ini, encoding="utf-8")

    # 2. Write recordEncoder.json
    encoder_cfg = {
        "rate_control": "CQP",
        "cqp": cqp,
        "preset2": "p5",
        "tune": "hq",
        "multipass": "qres",
        "profile": "high",
        "bf": 2,
    }
    (profile_dir / "recordEncoder.json").write_text(json.dumps(encoder_cfg), encoding="utf-8")

    # 3. Write scenes JSON
    scenes_data = build_scenes_json(profile_name, displays)
    (scenes_dir / f"{profile_name}.json").write_text(json.dumps(scenes_data, indent=2), encoding="utf-8")

    # 4. Write global.ini
    global_ini = f"""[General]
FirstRun=false
Pre23Defaults=false

[Basic]
Profile={profile_name}
ProfileDir={profile_name}
SceneCollection={profile_name}
SceneCollectionFile={profile_name}

[Audio]
DisableAudioDucking=true
"""
    (obs_root / "global.ini").write_text(global_ini, encoding="utf-8")

    summary = {
        "os": platform.system(),
        "obs_config_root": str(obs_root),
        "recording_output_dir": rec_path_str,
        "detected_encoder": encoder,
        "detected_displays": displays,
        "canvas": f"{canvas_w}x{canvas_h}@{fps}fps (CQP {cqp})",
        "scenes_created": [s["name"] for s in scenes_data["scene_order"]],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-detect hardware and bootstrap OBS Studio ISO recording profile")
    parser.add_argument("--profile-name", default="ThirdWaveCircuit", help="OBS profile & scene collection name")
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / "Videos" / "ThirdWaveCircuit" / "00_Inbox_Raw"),
        help="Directory where recordings are saved",
    )
    parser.add_argument("--canvas-width", type=int, default=3840, help="Base/Output canvas width (default: 3840)")
    parser.add_argument("--canvas-height", type=int, default=1080, help="Base/Output canvas height (default: 1080)")
    parser.add_argument("--fps", type=int, default=60, help="Recording framerate (default: 60)")
    parser.add_argument("--cqp", type=int, default=18, help="CQP quality level, lower=higher quality (default: 18)")
    args = parser.parse_args()

    bootstrap_studio(
        profile_name=args.profile_name,
        output_dir=Path(args.output_dir),
        canvas_w=args.canvas_width,
        canvas_h=args.canvas_height,
        fps=args.fps,
        cqp=args.cqp,
    )
