# 06 — 3D Gaussian Splatting Avatars (`06_gaussian_splatting_3dgs`)

## Overview
Next-generation volumetric 3D head and upper-body avatars built on **3D Gaussian Splatting (`GaussianAvatars`, `SplattingAvatar`, `GaussianSpeech`)**.

## How It Works
1. **FLAME 3DMM Tracking**: Tracks a parametric 3D head mesh (pose, shape, expression, jaw, and eyeball rotation) from `<session>_camera.mp4`.
2. **Rigged 3D Gaussians**: Binds anisotropic 3D Gaussians to the triangles of the FLAME mesh so they deform naturally with facial expressions and speech.
3. **Real-Time Differentiable Splatting**: Once an avatar splat field is trained, any future `<session>_camera.mp4` + `<session>_voice.wav` can drive the 3D avatar from **any virtual camera angle or focal length** with native 3D alpha transparency and zero temporal flicker.

## Hardware Requirements
- **Training / Fitting**: 12–24 GB VRAM CUDA GPU.
- **Inference / Rendering**: 30–100+ fps on 8–16 GB+ VRAM GPUs.
