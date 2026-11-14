---
name: studio-bootstrap
description: >-
  Use this skill when the user wants to set up, migrate, or customize the Third Wave Circuit
  recording and YouTube automation stack on a new computer, change OBS Studio settings
  (resolution, framerate, CQP quality, audio filters, monitor layout) via the CLI, or
  troubleshoot recording/post-processing scripts.
---

# Studio Bootstrap & Configuration Skill

This skill allows any AI agent to automatically detect a computer's displays, GPU encoder, OS paths, and audio devices, and configure **OBS Studio** + the **Third Wave Circuit** recording pipeline without hardcoded paths or manual GUI clicking.

## 1. Bootstrapping a New Machine or Updating OBS Settings

Run [configure_studio.py](./scripts/configure_studio.py) to auto-detect the host OS, GPU hardware encoder (`jim_nvenc`, `h264_texture_amf`, `obs_qsv11_v2`, Apple `VideoToolbox`, or `obs_x264`), and connected display resolutions, and write the OBS Studio profile and scene collection:

```bash
python .agents/skills/studio-bootstrap/scripts/configure_studio.py \
  --profile-name "ThirdWaveCircuit" \
  --canvas-width 3840 \
  --canvas-height 1080 \
  --fps 60 \
  --cqp 18
```

### Customizing Settings via CLI Flags
- **Change Recording Folder**: Pass `--output-dir "/path/to/recordings"`
- **Switch to 2×2 4K Grid (for 2 Monitors + Camera + Extra Source)**: Pass `--canvas-width 3840 --canvas-height 2160`
- **Adjust File Size vs. Quality**: Pass `--cqp 20` (smaller files) or `--cqp 16` (higher bitrate)
- **Change Framerate**: Pass `--fps 30` or `--fps 60`

## 2. Installing Dependencies (If Missing on Host)

1. **OBS Studio & FFmpeg**:
   - **Windows**: `winget install --id OBSProject.OBSStudio` and `winget install --id Gyan.FFmpeg`
   - **Linux (Ubuntu/Debian)**: `sudo apt install obs-studio ffmpeg`
   - **macOS**: `brew install --cask obs && brew install ffmpeg`
2. **Python Packages**:
   ```bash
   pip install -r requirements.txt
   ```

## 3. Verifying the Setup

After running `configure_studio.py`, verify the JSON summary printed to stdout:
1. Confirm `detected_encoder` matches the machine's GPU (`jim_nvenc` for NVIDIA, etc.).
2. Confirm `detected_displays` lists all connected monitors.
3. Launch a test recording session with `scripts/start_recording_session.ps1` (Windows) or `obs --profile ThirdWaveCircuit --collection ThirdWaveCircuit --startrecording` + `python scripts/track_context.py`.
