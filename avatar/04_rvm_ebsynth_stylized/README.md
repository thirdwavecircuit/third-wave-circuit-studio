# 04 — AI Video Matting + Stylized Shader / EbSynth (`04_rvm_ebsynth_stylized`)

## Overview
Instead of replacing the camera feed with a synthetic rig, this approach cuts the creator (and any held hardware, PCBs, or UV prints) out of `<session>_camera.mp4` without a green screen using **RobustVideoMatting (`RVM`)** or **BiRefNet**, and applies an artistic stylization pass.

## Best Use Cases
- Hardware build logs, soldering, or UV printing demos where **hands and physical objects** held up to the camera need to remain visible.
- Creating a cohesive stylized aesthetic (cyberpunk rim-lighting, halftone comic shader, blueprint edge-glow, or hand-painted rotoscoping).

## Two Stylization Modes
1. **Deterministic GPU/FFmpeg Shader (Zero Hallucination, Reusable)**:
   - Applies temporal bilateral filtering, luminance cel-shading, high-contrast line extraction, and brand-colored rim glow over the `RVM` alpha cutout.
2. **EbSynth Keyframe Paint-Over (Per-Clip Artistic Rotoscope)**:
   - Export 4–8 representative frames from `<session>_camera.mp4`, paint over them by hand in your chosen art style, and propagate the brush strokes across the entire video via optical-flow-guided texture synthesis (`EbSynth`).

## Hardware Requirements
- **Current Desktop / Entry GPU**: `RVM` + deterministic shader runs at 30–60 fps on a 4 GB VRAM GPU; `EbSynth` runs fast on CPU or GPU.
