# 02 — MediaPipe 52-Blendshape Layered Rig (`02_mediapipe_layered_rig`)

## Overview
A deterministic, zero-hallucination **60fps puppet & 3D VRM driver** powered by Google `MediaPipe FaceLandmarker` (478 3D landmarks + 52 Apple ARKit facial blendshapes), `_voice.wav` acoustic envelope analysis, and `track_context.py` window/input telemetry.

## How It Works
1. **Feature Extraction**:
   - Extracts continuous 60Hz curves from `<session>_camera.mp4`:
     - Head rotation (`pitch`, `yaw`, `roll`) and translation (`x`, `y`, `z`)
     - Eye blink & gaze (`eyeBlinkLeft`, `eyeBlinkRight`, `eyeLookInLeft`, `eyeLookOutRight`, etc.)
     - Brow motion (`browInnerUp`, `browDownLeft`, `browOuterUpRight`)
     - Mouth & jaw (`jawOpen`, `mouthSmileLeft`, `mouthPucker`, `mouthFunnel`)
   - Combines with `<session>_voice.wav` RMS amplitude and formant frequencies for crisp lip-sync even if the speaker turns slightly away from the camera.
   - Reads `<session>.jsonl` keyboard/mouse activity so the avatar can visibly type, move a stylus/mouse, or glance toward the active monitor.
2. **Layered 2D or 3D VRM Rendering**:
   - **2D Layered Mode**: Shifts and rotates separate transparent PNG layers (`body`, `head_base`, `eyes`, `pupils`, `brows`, `mouth`, `hair_front`) with 2.5D parallax.
   - **3D VRM Mode**: Drives standard `.vrm` / `.glb` blendshape targets headlessly onto a transparent RGBA buffer.

## Hardware Requirements
- **Any Hardware**: Runs at 60+ fps on CPU or entry-level 4 GB VRAM GPUs with 100% native alpha transparency.
