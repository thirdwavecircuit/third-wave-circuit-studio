# 03 — LivePortrait Implicit Keypoint Retargeting (`03_liveportrait_retargeting`)

## Overview
Uses **LivePortrait** (implicit 3D keypoint motion retargeting with stitching and eye/lip retargeting modules) to animate a **single static character illustration or portrait** (or a small multi-reference set) using the real performance captured in `<session>_camera.mp4`.

## Why Video-Driven Retargeting Matters for Technical Content
Unlike audio-only talking-head models that must guess head motion from speech alone, LivePortrait transfers your actual head tilts, code-reading glances, nods, and comedic timing directly from `<session>_camera.mp4` onto your artwork.

## Pipeline Stages
1. **Driving Crop & Stabilization**: Detects and stabilizes the face crop across `<session>_camera.mp4`.
2. **Implicit Keypoint Extraction & Retargeting**: Maps source illustration keypoints to the driving video motion trajectory (with optional lip/eye retargeting scalars).
3. **Alpha Matting (`RobustVideoMatting` / `BiRefNet`)**: Strips the background around the animated character so it composites cleanly over `<session>_screen.mp4`.

## Hardware Requirements
- **Current Desktop / Entry GPU**: Runs offline in FP16 on 4–6 GB VRAM GPUs (~3–8 fps on GTX 1650 SUPER).
- **Upgraded Desktop / Server GPU**: Runs at 25–50+ fps on RTX 4070/4080/4090/5090 class GPUs.
