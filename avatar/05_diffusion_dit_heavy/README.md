# 05 — Heavy Diffusion Transformers & Latent Lip-Sync (`05_diffusion_dit_heavy`)

## Overview
High-VRAM generative video pipelines designed for **server offloading (`devops/sync_drive_recordings.py`)** and **future workstation GPU upgrades (16–24+ GB VRAM)**.

## Supported Model Families
1. **End-to-End Audio + Pose Diffusion Transformers (`Hallo3` / `EchoMimicV2` / `HunyuanVideo-Avatar` / `Wan2.1-S2V`)**:
   - Takes **1 reference character image** + `<session>_voice.wav` + head/shoulder/hand pose trajectories extracted from `<session>_camera.mp4`.
   - Synthesizes full-frame portrait and upper-body animation with natural hair physics, lighting, and hand gestures.
2. **Audio-Driven Latent Lip-Sync Inpainting (`LatentSync` / `MuseTalk` / `Sonic`)**:
   - Designed for **post-recording voiceover patches (ADR)**: when you re-record or edit `<session>_voice.wav` without new camera footage, these models inpaint the mouth/jaw region of an existing avatar video loop in latent space to match the new audio track.

## Hardware Requirements
- **Latent Lip-Sync (`MuseTalk` / `LatentSync`)**: 8–12 GB VRAM.
- **Full DiT Avatar Generation (`Hallo3` / `EchoMimicV2` / `Wan2.1`)**: 16–24+ GB VRAM (RTX 3090 / 4080 / 4090 / 5090 or dedicated home server GPU).
