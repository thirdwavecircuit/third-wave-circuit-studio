# 🎬 Filming, Audio & Editing Playbook (Creative Tech & Maker Channels)

Best practices and production standards for **Third Wave Circuit** videos.

---

## 1. Pre-Flight Checklist (Before Hitting Record)

1. **Turn ON Windows "Do Not Disturb" (Focus Assist)**:
   - Prevents personal notifications, Discord popups, or emails from appearing on screen.
2. **The "Ctrl + Plus" Readability Rule**:
   - Over 50% of YouTube viewers watch on phones or small laptops.
   - Zoom VS Code, terminals, and browser tabs up **2–3 notches (`16pt–18pt` minimum)** so text is effortless to read.
   - Hide distracting IDE minimaps or file trees unless actively explaining them.
3. **Start Both Recorders**:
   - Launch **OBS Studio** (`Profile: ThirdWaveCircuit`) → click **Start Recording**.
   - Launch the telemetry sidecar in a terminal:
     ```powershell
     python .\scripts\track_context.py
     ```
4. **Use `[F9]` and `[F10]` While Working**:
   - Press **`[F9]`** whenever you say a great explanation, hit a funny bug, or get something working for the first time (marks a `HIGHLIGHT`).
   - Press **`[F10]`** whenever you move to the next major phase of the build (marks a `SECTION`).

---

## 2. Audio Engineering Standards (`-14 LUFS`)

Viewers will forgive imperfect video, but they click off bad audio in 3 seconds.

* **Target Loudness**: **`-14 LUFS`** integrated loudness with a **`-1.0 dBTP` True Peak ceiling** (automatically applied by `scripts/render_roughcut.py` via FFmpeg's `loudnorm` filter).
* **Recommended OBS Mic Filter Chain** (*Right-click `Mic/Aux` in OBS → Filters*):
  1. **Noise Suppression**: `RNNoise (good quality, more CPU usage)` — strips computer fan and room hum.
  2. **3-Band Equalizer / High-Pass**: Cut low rumble below `80 Hz`.
  3. **Compressor**: Ratio `3.5:1`, Threshold `-18 dB`, Attack `6 ms`, Release `60 ms` — keeps whispers and excited reactions at a consistent volume.
  4. **Limiter**: Threshold `-1.0 dB` — prevents clipping.
* **Mixing Levels in the Final Edit**:
  - **Voiceover / A-Roll**: `-14 LUFS` (peaks around `-3 dB` to `-6 dB`)
  - **Sound Effects (SFX / Whooshes / Pops)**: `-18 dB` to `-22 dB`
  - **Background Music (Synthwave / Lo-Fi / Ambient)**: `-26 dB` to `-30 dB` (subtle bed that never competes with speech)

---

## 3. The "1440p VP09 Codec Trick" for Crisp Code

When you upload a `1920×1080` video to a newer channel, YouTube often compresses it with the older `avc1` codec, which turns small terminal text and dark-mode code into blurry blocks.

* **The Fix**: Export your final video (or run `render_roughcut.py --upscale-1440p`) at **`2560×1440` (1440p)** using Lanczos scaling.
* Uploading at `2560×1440` forces YouTube to encode your video with the **`VP09` / `AV01` codec**, giving your video roughly **2x–3x higher visual sharpness** for dark-mode terminals and detailed art textures.

---

## 4. Pacing, Hooks & Storytelling for Tech/Maker Videos

1. **The First 5 Seconds (Payoff First)**:
   - Never open with *"Hey guys, welcome back to my channel, today we're going to..."*
   - Show the **working result or core visual question** in the first 5 seconds, then rewind to show how you built it.
2. **Visual Pattern Interrupts (Every 6–10 Seconds)**:
   - Alternate between:
     - **Full Screen view** (context)
     - **Active Window / Cursor Zoom** (detail)
     - **Avatar / Camera view** (personality & explanation)
     - **Architecture Diagrams** (Excalidraw / Mermaid animations)
     - **Physical / Macro B-Roll** (for UV printing, hardware, or sensors)
3. **Kill Dead Air (`analyze_session.py`)**:
   - Keep spoken explanations at `1.0x`, and compress silent coding/drawing stretches into `8x–20x` timelapses with music underneath.

---

## 5. Recommended Free & Open-Source Creator Tools

| Category | Tool | Why It's Great |
| :--- | :--- | :--- |
| **Video Editor (NLE)** | **DaVinci Resolve (Free)** | Reads embedded Hybrid MP4 chapter markers natively; world-class color, Fairlight audio, and Fusion motion graphics. |
| **Instant Trimming** | **LosslessCut** (`github.com/mifi/lossless-cut`) | Open-source tool to slice/trim multi-hour recordings in milliseconds without re-encoding. |
| **Diagrams & Whiteboard** | **Excalidraw** (`excalidraw.com`) | Hand-drawn style architecture diagrams that look great in dark mode. |
| **Code-Driven Animation** | **Motion Canvas** (`motioncanvas.io`) / **Manim** | Write TypeScript or Python code to generate 60fps technical animations and state diagrams. |
| **Audio / Music** | **YouTube Studio Audio Library** / **StreamBeats** | 100% DMCA-safe instrumental tracks that will never copyright-claim your channel. |
