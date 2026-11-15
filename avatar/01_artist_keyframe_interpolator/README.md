# 01 — Artist Keyframe Interpolator (`01_artist_keyframe_interpolator`)

## Overview
Designed for artists who want **100% control over their hand-drawn line art and aesthetic** under a **"Draw Once, Use Forever"** workflow.

Instead of relying on a single-image generative model to hallucinate mouth interiors, closed eyelids, or head turns, the artist draws a small reusable **Character Pose Sheet** (typically 6 to 12 frames on a transparent canvas). Every future recording automatically drives and interpolates between those drawings using `<session>_camera.mp4` and `<session>_voice.wav`.

## Asset Specification (Drawn Once)
Place transparent PNG drawings (`1024x1024` or `2048x2048` RGBA) in an asset pack directory:
- `neutral_closed.png` — Base resting pose, eyes open, mouth closed
- `neutral_blink.png` — Eyes closed
- `talk_small.png` — Slight mouth opening / consonant shape
- `talk_open_ah.png` — Wide open vowel shape (`ah`)
- `talk_round_oh.png` — Rounded vowel shape (`oh` / `oo`)
- `talk_smile_ee.png` — Wide smile / `ee` shape
- `look_code_monitor.png` — Glancing toward the primary coding display
- `focused_squint.png` — Concentrated / debugging expression

## Interpolation Modes
1. **Stepped Indie / Anime Hold (`12fps` / `24fps` on `60fps` timeline)**:
   - Snappy, intentional hand-drawn frame switching driven by hysteresis-smoothed voice visemes, blink detection, and head yaw, plus subtle 2D spring physics (breathing, voice-reactive bounce, head tilt from `_camera.mp4`).
2. **Thin-Plate Spline (TPS) & Optical Flow Morphing**:
   - Uses facial landmark correspondence + Thin-Plate Spline warping / RIFE optical flow to generate smooth 60fps in-betweens between the nearest hand-drawn poses while applying continuous head pitch/yaw/roll transforms.
3. **Pre-Baked Neural Transition Atlas (`ToonCrafter` / `AniDoc`)**:
   - Uses a cartoon line-art diffusion interpolator (`ToonCrafter`) **once** to pre-render fluid hand-drawn transitions between every pair of poses ($A \leftrightarrow B$), caching the transition atlas locally so future recordings render rapidly on any hardware.

## Hardware Requirements
- **Stepped / TPS / Optical Flow**: Runs faster than real-time on CPU or 4 GB VRAM GPU.
- **ToonCrafter Transition Atlas Pre-Bake**: Best run once on a 12–24 GB VRAM GPU (or server); once cached, daily video rendering requires only CPU / 4 GB VRAM.
