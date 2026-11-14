---
name: studio-bootstrap
description: >-
  Use this skill when the user wants to set up, migrate, or customize the Third Wave Circuit
  recording and YouTube automation stack, change OBS Studio settings via CLI, or run
  recording, telemetry, privacy-audit, editing, captioning, or YouTube GitOps workflows.
---

# Third Wave Circuit Studio — Dynamic Agent Skill

> **Anti-Drift Rule**: Do **not** rely on hardcoded paths, flags, or static config templates. Always discover the active `third-wave-circuit-studio` repository root and query the scripts directly via `--help` (`-?` for PowerShell).

## 1. Locate or Clone the Repository (Single Source of Truth)

1. Check if the current workspace is already inside `third-wave-circuit-studio` (contains `scripts/configure_studio.py` and `youtube-gitops/sync_video.py`).
2. If running from another workspace, locate the local clone (e.g., search `~` or `$HOME` for `third-wave-circuit-studio`), or clone the latest upstream:
   ```bash
   git clone https://github.com/thirdwavecircuit/third-wave-circuit-studio.git
   ```
3. Before making changes or running workflows, check `git status` / `git pull` so you are always using the latest scripts.

## 2. Dynamic Capability Discovery

Rather than assuming hardcoded flags or parameters, discover available tools and their live CLI signatures directly from the repository:

1. **Read Repository Index & Standards**:
   - Read `README.md` at the repo root for the current directory map and workflow overview.
   - Read `docs/FILMING_AND_EDITING_PLAYBOOK.md` for current audio (`LUFS`), video codec, and editing rules.
2. **Query Script CLI Signatures Dynamically**:
   - **Python tools** (`scripts/*.py`, `youtube-gitops/*.py`): Run `python <script.py> --help` to inspect current flags and defaults.
   - **PowerShell tools** (`scripts/*.ps1`): Read the `param(...)` block at the top of `<script.ps1>` to inspect current parameters and defaults.

## 3. Core Workflows (By Script Role)

- **Bootstrap / Reconfigure OBS Studio (OS, GPU & Monitors Auto-Detected)**:
  Run `python scripts/configure_studio.py --help` to see all customizable parameters (canvas resolution, framerate, CQP quality, profile name, output directory), then execute `scripts/configure_studio.py` to generate OBS Studio's `global.ini`, `basic.ini`, `recordEncoder.json`, and `scenes.json` dynamically.
- **Start Synchronized Recording + Telemetry**:
  Run `scripts/start_recording_session.ps1` (which auto-bootstraps OBS if needed, finds `obs64` dynamically, starts recording, and launches `scripts/track_context.py`).
- **Post-Processing & Publishing**:
  Discover and run the pipeline scripts in `scripts/` (`audit_privacy.py`, `split_streams.ps1`, `analyze_session.py`, `render_roughcut.py`, `auto_captions.py`, `sync_to_shared.ps1`) and `youtube-gitops/` (`sync_video.py`, `fetch_analytics.py`).
