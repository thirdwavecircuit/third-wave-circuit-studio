# ⚡ Third Wave Circuit Studio

**Description:** Open-source synchronized ISO recording, window/cursor telemetry, privacy auditing, media post-processing, and declarative YouTube GitOps automation stack powering the **Third Wave Circuit** channel.

---

## 📦 Architecture & Contents

```text
third-wave-circuit-studio/
├── docs/
│   └── FILMING_AND_EDITING_PLAYBOOK.md  # Audio (-14 LUFS), 1440p VP09 trick, pacing & free tools
├── obs-profile/                         # Portable OBS profile (3840x1080 ISO canvas, Hybrid MP4, NVENC CQP 18)
│   ├── basic.ini
│   └── recordEncoder.json
├── scripts/
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
├── LICENSE                              # MIT License
└── requirements.txt
```

---

## 🎥 1. Synchronized ISO Recording + Telemetry Sidecar

Instead of cropping windows live or burning a webcam overlay over your screen pixels, this stack captures **every signal independently and frame-locked**:

1. **OBS `3840×1080` Side-by-Side Canvas (`obs-profile/`)**:
   - **Left Half (`0..1920`)**: Clean full-display `1920×1080` screen capture.
   - **Right Half (`1920..3840`)**: Clean full-resolution `1920×1080` raw webcam/face output.
   - **Container**: `hybrid_mp4` (crash-safe like `.mkv`, plus native MP4 chapter marker support).
   - **Encoder**: `NVIDIA NVENC H.264` (`CQP = 18` — visually lossless, scales bitrate dynamically).
   - **Multi-Track Audio**:
     - **Track 1**: Master Mix (Mic + Desktop)
     - **Track 2**: Microphone Only (isolated for voice activity detection & processing)
     - **Track 3**: Desktop Audio Only (isolated application audio)

2. **Window, Cursor & Marker Telemetry (`scripts/track_context.py`)**:
   Run alongside OBS while recording:
   ```powershell
   python .\scripts\track_context.py
   ```
   Logs a 10Hz `*_telemetry.jsonl` sidecar containing:
   - Active window title & exact pixel bounding box (`x, y, w, h`) — lets you crop to a single window/tab *after* recording.
   - Mouse cursor `(x, y)` & click state — enables smooth cursor auto-zoom in post.
   - **`[F9]` Hotkey**: Drops a timestamped `HIGHLIGHT` marker (great take, bug, key reveal).
   - **`[F10]` Hotkey**: Drops a timestamped `SECTION` marker (new chapter / build step).

---

## 🛠️ 2. Post-Processing, Privacy Audit & Editable Timeline (`scripts/`)

```powershell
# 1. Audit telemetry for any accidental sensitive windows (.env, passwords, email, chats)
python .\scripts\audit_privacy.py --telemetry "session_telemetry.jsonl"

# 2. Split the 3840x1080 recording into 4 frame-locked files (_screen.mp4, _camera.mp4, _voice.wav, _desktop.wav)
.\scripts\split_streams.ps1 -InputFile "session.mp4"

# 3. Analyze isolated voice + window telemetry into an editable YAML edit plan (non-destructive!)
python .\scripts\analyze_session.py --voice "session_voice.wav" --telemetry "session_telemetry.jsonl"

# 4. (Optional) Render rough cut from your reviewed YAML plan (-14 LUFS normalized + 1440p VP09 upscale)
python .\scripts\render_roughcut.py --plan "session_edit_plan.yaml" --screen "session_screen.mp4" --out "roughcut.mp4" --upscale-1440p

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
