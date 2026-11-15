---
name: studio-bootstrap
description: >-
  Use this skill when the user wants to set up, migrate, or customize the Third Wave Circuit
  recording and YouTube automation stack, change OBS Studio settings via CLI, or run
  recording, telemetry, privacy-audit, editing, captioning, or YouTube GitOps workflows.
---

# Third Wave Circuit Studio — Dynamic Agent Skill

> **Anti-Drift & Testing-First Rule**:
> 1. Do **not** rely on hardcoded paths, flags, or static config templates. Always discover the active `third-wave-circuit-studio` repository root and query the scripts directly via `--help` (`-?` for PowerShell).
> 2. **Testing First**: Whenever adding or modifying any script or feature in this repository, you **must** add/update unit & regression tests in `tests/` and verify `python3 -m unittest discover -s tests -v` passes 100% before committing.

## 1. Locate or Clone the Repository (Single Source of Truth)

1. Check if the current workspace is already inside `third-wave-circuit-studio` (contains `recording/configure_studio.py`, `post-processing/analyze_session.py`, and `youtube-gitops/sync_video.py`).
2. If running from another workspace, locate the local clone (e.g., search `~` or `$HOME` for `third-wave-circuit-studio`), or clone the latest upstream:
   ```bash
   git clone https://github.com/thirdwavecircuit/third-wave-circuit-studio.git
   ```
3. Before making changes or running workflows, check `git status` / `git pull` so you are always using the latest scripts.

## 2. Dynamic Capability Discovery

Rather than assuming hardcoded flags or parameters, discover available tools and their live CLI signatures directly from the repository's three modular directories (`recording/`, `post-processing/`, `youtube-gitops/`):

1. **Read Repository Index & Standards**:
   - Read `README.md` at the repo root for the current directory map and workflow overview.
   - Read `docs/FILMING_AND_EDITING_PLAYBOOK.md` for current audio (`LUFS`), video codec, and editing rules.
2. **Query Script CLI Signatures Dynamically**:
   - **Python tools** (`recording/*.py`, `post-processing/*.py`, `youtube-gitops/*.py`): Run `python <script.py> --help` to inspect current flags and defaults.
   - **PowerShell tools** (`recording/*.ps1`, `post-processing/*.ps1`): Read the `param(...)` block at the top of `<script.ps1>` to inspect current parameters and defaults.

## 3. Core Workflows (By Module)

- **Phase 1 — Raw Multi-Track Capture & Extraction (`recording/`)**:
  - `recording/configure_studio.py`: Auto-detects OS, GPU encoder, and connected displays to generate OBS Studio's `global.ini`, `basic.ini`, `recordEncoder.json`, and `scenes.json`.
  - `recording/start_recording_session.ps1`: Launches OBS Studio + `recording/track_context.py` (`10Hz` window, monitor, cursor, activity, and `F9`/`F10` marker logger).
  - `recording/split_streams.ps1`: Splits the `3840x1080` capture into 4 standalone files (`_screen.mp4`, `_camera.mp4`, `_voice.wav`, `_desktop.wav`).
  - `recording/recompile_streams.py`: 1:1 (`1.0x`) sanity-check recompiler that recombines the 4 separated streams with zero speed-ramping or cuts.
- **Phase 2 — Offline Alignment, Privacy Audit & Composition (`post-processing/`)**:
  - `post-processing/audit_privacy.py`: Scans `*_telemetry.jsonl` for accidental sensitive window titles.
  - `post-processing/analyze_session.py`: Aligns voice + telemetry onto the shared `OBS_FILE_START` master clock (`*_enriched_telemetry.jsonl`) and generates `*_edit_plan.yaml`.
  - `post-processing/render_roughcut.py`: Renders `*_edit_plan.yaml` (offline avatar PiP overlay, active window crop, timelapse speed-ramping, `-14 LUFS`, `1440p` VP09 upscale).
  - `post-processing/auto_captions.py`.
- **Phase 3 — Multi-Machine Cloud & Storage Sync (`devops/`)**:
  - `devops/sync_drive_recordings.py`: Pushes (`--action push`) or pulls (`--action pull`) raw & split recording components via Google Drive (`12 Media/Uploads/recordings/<session>/`) with MD5 verification so post-processing can run on either the desktop or a home server.
  - `devops/sync_to_shared.ps1`: Syncs recordings to LAN/NAS storage.
- **Phase 4 — Declarative YouTube GitOps (`youtube-gitops/`)**:
  - `youtube-gitops/sync_video.py` & `youtube-gitops/fetch_analytics.py`.
