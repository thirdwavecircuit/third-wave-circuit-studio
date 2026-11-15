# ⚡ Third Wave Circuit Studio

**Description:** Open-source synchronized ISO recording, hardware auto-discovery, window/cursor telemetry, privacy auditing, media post-processing, and declarative YouTube GitOps automation stack powering the **Third Wave Circuit** channel.

---

## 📦 Architecture & Contents

```text
third-wave-circuit-studio/
├── .agents/skills/studio-bootstrap/
│   └── SKILL.md                         # Dynamic Agent Skill (zero-drift repo & CLI discovery)
├── docs/
│   └── FILMING_AND_EDITING_PLAYBOOK.md  # Audio (-14 LUFS), 1440p VP09 trick, pacing & free tools
├── scripts/
│   ├── configure_studio.py              # Auto-detects OS, GPU & monitors -> writes OBS profile & scenes
│   ├── start_recording_session.ps1      # One-command launcher for OBS (--startrecording) + telemetry
│   ├── track_context.py                 # 10Hz Window bounds, mouse cursor & F9/F10 marker sidecar logger
│   ├── audit_privacy.py                 # Pre-edit OPSEC scanner for sensitive window titles in telemetry
│   ├── split_streams.ps1                # Splits 3840x1080 recording into screen, camera, voice & desktop files
│   ├── analyze_session.py               # Combines voice activity + telemetry into an editable *_edit_plan.yaml
│   ├── render_roughcut.py               # Renders *_edit_plan.yaml with -14 LUFS audio & optional 1440p upscale
│   ├── auto_captions.py                 # Local Whisper .srt subtitle & searchable JSON transcript generator
│   ├── process_recording.ps1            # Remux, NVENC timelapse generator & isolated mic extractor
│   └── sync_to_shared.ps1               # Multi-threaded robocopy mirror to shared NAS / network storage
├── youtube-gitops/                      # Declarative YouTube Data API v3 & Analytics v2 pipeline
│   ├── sync_video.py                    # Syncs video.yaml manifests to YouTube Studio
│   ├── fetch_analytics.py               # Pulls channel & per-video performance metrics
│   └── example_video.yaml               # Declarative video metadata template
├── tests/                               # Automated Unit, Integration & OPSEC Regression Suite
│   ├── test_studio_pipeline.py          # Tests OBS generation, WAV voice segmentation, telemetry & SRT
│   └── test_repo_hygiene.py             # Guards against hardcoded paths, LAN IPs & broken CLI flags
├── .github/workflows/ci.yml             # GitHub Actions CI runner on every push/PR
├── LICENSE                              # MIT License
└── requirements.txt
```

---

## 🤖 0. One-Command Agent / CLI Bootstrap (Any Computer)

Instead of static, hardcoded config files that drift over time, `scripts/configure_studio.py` dynamically inspects the host OS, GPU hardware encoder (`NVENC`, `AMF`, `QSV`, `VideoToolbox`, or `x264`), and connected display resolutions to generate the OBS Studio profile (`basic.ini`, `recordEncoder.json`), 3-track audio routing, mic filter chain (`RNNoise` → `Compressor` → `Limiter`), and ISO scenes (`scenes.json`):

```bash
python scripts/configure_studio.py --help
python scripts/configure_studio.py
```

If you open this repository with an AI coding agent, it will automatically load [.agents/skills/studio-bootstrap/SKILL.md](.agents/skills/studio-bootstrap/SKILL.md) to discover and run all scripts dynamically.

---

## 🎥 1. Phase 1: Raw Multi-Track Data Collection (Shared Master Clock)

Instead of baking overlays or running GPU-heavy AI avatars live during recording, OBS Studio and `track_context.py` operate strictly as **synchronized raw multi-track sensors** locked to a single master clock (`OBS_FILE_START` aligns `t_ms = 0`):

```powershell
.\scripts\start_recording_session.ps1
```

What gets captured simultaneously and independently:
- **Left Half (`0..1920`)**: Clean full-display screen capture (defaults to your highest-resolution working monitor).
- **Right Half (`1920..3840`)**: Clean full-resolution raw webcam/face output (used in post to drive offline AI avatar generation or PiP).
- **Audio Track 1**: Master Mix (Mic + Desktop)
- **Audio Track 2**: Microphone Only (isolated with `RNNoise`, `3.5:1 Compressor`, and `-1.0 dB Limiter`)
- **Audio Track 3**: Desktop Audio Only (isolated application audio)
- **10Hz Telemetry Sidecar (`*_telemetry.jsonl`)**:
  - `active_monitor` & `cursor_monitor` (`1` or `2`) — tracks which monitor you are working on at every 100ms tick.
  - `is_active_input` & `idle_ms` — privacy-safe keyboard/mouse activity signal (via `GetLastInputInfo`, zero keylogging).
  - `window` (`title`, `rect: {x, y, w, h}`) — lets post-processing crop to a specific window/IDE tab *after* recording.
  - `cursor` (`x, y, lmb, rmb`) — enables smooth cursor auto-zoom and click-triggered zooms in post.
  - **`[F9]` Hotkey**: Drops a timestamped `HIGHLIGHT` marker.
  - **`[F10]` Hotkey**: Drops a timestamped `SECTION` marker.

---

## 🛠️ 2. Phase 2: Offline Master-Clock Alignment & Layout Composition (`scripts/`)

```powershell
# 1. Audit telemetry for any accidental sensitive windows (.env, passwords, email, chats)
python .\scripts\audit_privacy.py --telemetry "session_telemetry.jsonl"

# 2. Split the 3840x1080 recording into 4 frame-locked files (_screen.mp4, _camera.mp4, _voice.wav, _desktop.wav)
.\scripts\split_streams.ps1 -InputFile "session.mp4"

# 3. Merge voice activity (is_speaking, voice_db) onto the 10Hz telemetry (*_enriched_telemetry.jsonl)
#    and generate a declarative *_edit_plan.yaml with active_monitor, window bounds & avatar_overlay config
python .\scripts\analyze_session.py --voice "session_voice.wav" --telemetry "session_telemetry.jsonl"

# 4. (Optional) Compose & render rough cut from your YAML plan (layers offline avatar PiP, crops to active_window, -14 LUFS & 1440p VP09)
python .\scripts\render_roughcut.py --plan "session_edit_plan.yaml" --screen "session_screen.mp4" --avatar "session_camera.mp4" --out "roughcut.mp4" --upscale-1440p

# 5. Generate local .srt subtitles and searchable word transcript via Whisper
python .\scripts\auto_captions.py --voice "session_voice.wav" --model base

# 6. Sync completed recordings & project assets to shared network storage
.\scripts\sync_to_shared.ps1 -SharedPath "\\nas.local\media\ThirdWaveCircuit"
```

---

## 🚀 3. Declarative YouTube GitOps (`youtube-gitops/`)

Manage video titles, descriptions, links, tags, thumbnails, and chapter timestamps as code via `video.yaml`:

```bash
pip install -r requirements.txt

# Publish or update video metadata & thumbnail from YAML
python youtube-gitops/sync_video.py --manifest youtube-gitops/example_video.yaml

# Pull 28-day channel & video analytics report
python youtube-gitops/fetch_analytics.py --days 28 --out analytics_report.json
```

---

## 📚 4. Filming & Editing Playbook

See [docs/FILMING_AND_EDITING_PLAYBOOK.md](docs/FILMING_AND_EDITING_PLAYBOOK.md) for:
- Pre-flight recording checklist & OBS mic filter chain (`RNNoise` → `80Hz High-Pass` → `Compressor` → `-1.0 dB Limiter`)
- The **1440p VP09 Codec Trick** for razor-sharp dark-mode terminal and IDE text
- Pacing, visual pattern interrupts, and free open-source tools (**DaVinci Resolve**, **LosslessCut**, **Excalidraw**, **Motion Canvas**)
