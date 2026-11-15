# Offline Avatar Generation (`avatar/`)

This module contains offline post-processing approaches for generating a synchronized creator avatar driven by the decoupled sensor tracks captured in `recording/`:

- **`<session>_camera.mp4`** (`1920x1080@60fps` isolated camera stream): Provides facial landmarks, 52 ARKit blendshapes, eye gaze, head pose (pitch/yaw/roll), and upper-body/hand silhouettes.
- **`<session>_voice.wav`** (`48kHz` isolated microphone track): Provides clean speech amplitude envelopes, phoneme/viseme timing, and acoustic conditioning completely free of desktop audio bleed.
- **`<session>.jsonl`** (`10Hz` window & input telemetry): Provides active monitor, cursor position, and keyboard/mouse activity for context-aware avatar states (e.g., looking toward the active code display or triggering typing animations).

By running avatar synthesis **offline in post-processing**, zero GPU/VRAM overhead is placed on the workstation during live screen/hardware recording, and heavy neural approaches can be offloaded to a home server or higher-VRAM workstation via `devops/sync_drive_recordings.py`.

---

## Comparison of Avatar Approaches

| Folder | Paradigm | Reusable ("Draw Once, Use Forever")? | Driving Inputs | Alpha Overlay | Hardware Tier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [`01_artist_keyframe_interpolator/`](./01_artist_keyframe_interpolator/) | **Hand-Drawn Pose Sheet + Optical Flow / TPS / ToonCrafter Atlas** | **Yes** (6–12 hand-drawn frames reused across all future videos) | `_camera.mp4` + `_voice.wav` | Native 100% clean alpha | **Any** (CPU / 4 GB+ GPU; optional high-VRAM pre-baked transition atlas) |
| [`02_mediapipe_layered_rig/`](./02_mediapipe_layered_rig/) | **52 ARKit Blendshapes + Layered 2D Puppet / 3D VRM** | **Yes** (layered PSD/PNG parts or `.vrm` model reused forever) | `_camera.mp4` + `_voice.wav` + `.jsonl` | Native 100% clean alpha | **Any** (CPU or 4 GB+ GPU at 60+ fps) |
| [`03_liveportrait_retargeting/`](./03_liveportrait_retargeting/) | **Implicit Keypoint Neural Retargeting (`LivePortrait`)** | **Yes** (1–4 static character illustrations reused forever) | `_camera.mp4` motion + `_voice.wav` | Secondary matting (`RVM` / `BiRefNet`) | **Entry / Mid GPU** (4–8 GB VRAM in FP16) |
| [`04_rvm_ebsynth_stylized/`](./04_rvm_ebsynth_stylized/) | **AI Video Matting (`RVM`) + Stylized Shader / `EbSynth` Paint-Over** | Shader is reusable; `EbSynth` keyframes are per-clip | `_camera.mp4` full silhouette + hands/props | Direct alpha matte (`RVM`) | **Entry / Mid GPU** (`RVM` runs 60fps on 4 GB VRAM) |
| [`05_diffusion_dit_heavy/`](./05_diffusion_dit_heavy/) | **End-to-End Diffusion Transformers (`Hallo3`, `EchoMimicV2`, `LatentSync`, `Wan2.1`)** | **Yes** (single reference image + audio/pose conditioning) | `_voice.wav` + `_camera.mp4` pose skeleton | Chroma/Matte extraction | **High-VRAM Server / Future GPU** (16–24+ GB VRAM) |
| [`06_gaussian_splatting_3dgs/`](./06_gaussian_splatting_3dgs/) | **Rigged 3D Gaussian Splatting (`GaussianAvatars` / `SplattingAvatar`)** | **Yes** (once 3DGS avatar is trained) | `_camera.mp4` FLAME 3DMM + `_voice.wav` | Native 3D splat alpha | **High-VRAM Server / Future GPU** (12–24 GB VRAM) |

---

## Shared Conditioning Contract

All approaches in `avatar/` are designed around a shared session conditioning timeline locked to `OBS_FILE_START` (`t_ms = 0`):

1. **Performance Extraction**: Extract per-frame facial blendshapes (52 ARKit channels), 3D head pose Euler angles, eye gaze vectors, and voice RMS/viseme weights from `<session>_camera.mp4` and `<session>_voice.wav`.
2. **Avatar Stream Synthesis**: Render an alpha-transparent avatar stream (`<session>_avatar.mov` / `yuva420p` `.webm`) matching the exact frame count and frame rate of `<session>_screen.mp4`.
3. **Final Compositing (`post-processing/render_roughcut.py`)**: Composite `<session>_avatar` over `<session>_screen.mp4` in place of (or alongside) the raw camera track.
