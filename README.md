# ⚡ Third Wave Circuit Studio

**Description:** Open-source recording, media processing, and declarative YouTube GitOps automation stack powering the **Third Wave Circuit** channel.

---

## 📦 Architecture & Contents

```text
third-wave-circuit-studio/
├── obs-profile/                # Portable OBS Studio profile (NVENC CQP 18, 60fps, 3-track audio)
│   ├── basic.ini
│   └── recordEncoder.json
├── scripts/
│   ├── process_recording.ps1   # Remux .mkv -> .mp4, generate NVENC timelapses, extract isolated mic
│   └── sync_to_shared.ps1      # Sync completed local recordings to shared NAS / network storage
├── youtube-gitops/             # Declarative YouTube Data API v3 & Analytics pipeline
│   ├── sync_video.py           # Syncs video.yaml manifests to YouTube Studio
│   └── example_video.yaml      # Declarative video metadata template
└── requirements.txt
```

---

## 🎥 1. Crash-Proof Local Recording + Shared Storage Sync

> **Why record locally first?** Recording 60fps high-bitrate video directly over SMB/NFS network shares can drop frames or corrupt files if the network hiccups. Instead, OBS records locally to SSD (`00_Inbox_Raw/`), and `scripts/sync_to_shared.ps1` automatically mirrors completed takes to shared network storage.

### Install the OBS Profile
Copy `obs-profile/` into your OBS Studio profiles directory (`%APPDATA%\obs-studio\basic\profiles\ThirdWaveCircuit\` on Windows or `~/.config/obs-studio/basic/profiles/ThirdWaveCircuit/` on Linux):
- **Container**: `.mkv` (crash-safe—never lose a multi-hour build recording if an app crashes)
- **Encoder**: `NVIDIA NVENC H.264` (`CQP = 18` — visually lossless quality that dynamically scales bitrate)
- **Multi-Track Separated Audio**:
  - **Track 1**: Master Mix (Mic + Desktop)
  - **Track 2**: Microphone Only (isolated for silence removal & voice processing)
  - **Track 3**: Desktop Audio Only (isolated system/application audio)

---

## 🛠️ 2. Media Post-Processing (`scripts/`)

```powershell
# Losslessly remux .mkv to .mp4 for editing
.\scripts\process_recording.ps1 -InputFile "raw.mkv" -Action remux

# Turn a 1-hour silent drawing/coding session into a 3-minute 20x NVENC timelapse
.\scripts\process_recording.ps1 -InputFile "raw.mkv" -Action timelapse -SpeedMultiplier 20

# Extract isolated Microphone track (Track 2) as WAV
.\scripts\process_recording.ps1 -InputFile "raw.mkv" -Action extract-mic

# Sync completed recordings & project assets to shared network storage
.\scripts\sync_to_shared.ps1 -SharedPath "\\nas.local\media\ThirdWaveCircuit"
```

---

## 🚀 3. Declarative YouTube GitOps (`youtube-gitops/`)

Manage video titles, descriptions, links, tags, thumbnails, and chapter timestamps as code via `video.yaml`:

```bash
pip install -r requirements.txt
python youtube-gitops/sync_video.py --manifest youtube-gitops/example_video.yaml
```
