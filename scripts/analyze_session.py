#!/usr/bin/env python3
"""
Session Analyzer & Edit Plan Generator (`analyze_session.py`)

Reads the isolated microphone track (`*_voice.wav`) and telemetry sidecar (`*_telemetry.jsonl`)
from a recording session and produces a declarative `*_edit_plan.yaml` file.

Instead of blindly cutting or speeding up your video, this gives you a structured timeline of:
  - Spoken segments (`voice_active: true`, suggested `speed: 1.0`)
  - Silent coding/drawing stretches (`voice_active: false`, suggested `speed: 8.0` timelapse)
  - F9 (HIGHLIGHT) & F10 (SECTION) markers pressed during recording
  - Dominant active window & bounding box for each segment (`view_mode: full_screen | active_window | cursor_zoom`)

You can then tweak `*_edit_plan.yaml` by hand and feed it to your renderer whenever you're ready.
"""

import argparse
import json
import math
import os
import struct
import wave
from collections import Counter
import yaml


def analyze_wav_activity(wav_path: str, window_sec: float = 0.5, silence_db: float = -38.0):
    """Returns a list of booleans indicating voice activity per `window_sec` chunk."""
    with wave.open(wav_path, "rb") as wf:
        rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        frames_per_chunk = int(rate * window_sec)

        activity = []
        while True:
            raw = wf.readframes(frames_per_chunk)
            if not raw:
                break
            if sampwidth == 2:
                samples = struct.unpack(f"<{len(raw) // 2}h", raw)
                if not samples:
                    break
                rms = math.sqrt(sum(s * s for s in samples) / len(samples))
                db = 20 * math.log10(max(rms, 1.0) / 32768.0)
                activity.append(db > silence_db)
            else:
                activity.append(True)
    return activity, window_sec


def load_telemetry(jsonl_path: str):
    events = []
    if not jsonl_path or not os.path.exists(jsonl_path):
        return events
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_edit_plan(wav_path: str, telemetry_path: str = None, min_silence_sec: float = 3.0):
    activity, step = analyze_wav_activity(wav_path)
    telemetry = load_telemetry(telemetry_path)

    raw_segments = []
    for idx, is_active in enumerate(activity):
        t_start = idx * step
        t_end = (idx + 1) * step
        if raw_segments and raw_segments[-1]["voice_active"] == is_active:
            raw_segments[-1]["end_sec"] = t_end
        else:
            raw_segments.append({
                "start_sec": t_start,
                "end_sec": t_end,
                "voice_active": is_active,
            })

    merged = []
    for seg in raw_segments:
        dur = seg["end_sec"] - seg["start_sec"]
        if not seg["voice_active"] and dur < min_silence_sec and merged:
            merged[-1]["end_sec"] = seg["end_sec"]
        elif merged and merged[-1]["voice_active"] == seg["voice_active"]:
            merged[-1]["end_sec"] = seg["end_sec"]
        else:
            merged.append(seg)

    plan_segments = []
    markers_summary = []

    for e in telemetry:
        if e.get("marker"):
            t_s = e["t_ms"] / 1000.0
            markers_summary.append({
                "time": fmt_time(t_s),
                "time_sec": round(t_s, 2),
                "type": e["marker"],
                "window": (e.get("window") or {}).get("title", ""),
            })

    for i, seg in enumerate(merged):
        s_ms = seg["start_sec"] * 1000
        e_ms = seg["end_sec"] * 1000
        seg_events = [e for e in telemetry if s_ms <= e.get("t_ms", 0) <= e_ms]

        titles = [
            (e.get("window") or {}).get("title", "")
            for e in seg_events
            if (e.get("window") or {}).get("title")
        ]
        dominant_window = Counter(titles).most_common(1)[0][0] if titles else "Desktop"
        seg_markers = [e["marker"] for e in seg_events if e.get("marker")]

        plan_segments.append({
            "id": i + 1,
            "start": fmt_time(seg["start_sec"]),
            "end": fmt_time(seg["end_sec"]),
            "duration_sec": round(seg["end_sec"] - seg["start_sec"], 1),
            "voice_active": seg["voice_active"],
            "dominant_window": dominant_window,
            "markers": seg_markers,
            "action": "keep" if seg["voice_active"] else "timelapse",
            "speed": 1.0 if seg["voice_active"] else 8.0,
            "view_mode": "full_screen",  # Options: full_screen | active_window | cursor_zoom
            "show_avatar": seg["voice_active"],
        })

    return {
        "source_voice": os.path.basename(wav_path),
        "source_telemetry": os.path.basename(telemetry_path) if telemetry_path else None,
        "markers": markers_summary,
        "segments": plan_segments,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze isolated voice WAV + window telemetry into an editable YAML plan")
    parser.add_argument("--voice", required=True, help="Path to isolated *_voice.wav (Track 2)")
    parser.add_argument("--telemetry", help="Path to *_telemetry.jsonl")
    parser.add_argument("--out", help="Output YAML path (defaults to *_edit_plan.yaml)")
    args = parser.parse_args()

    out_path = args.out or args.voice.replace("_voice.wav", "_edit_plan.yaml")
    plan = build_edit_plan(args.voice, args.telemetry)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(plan, f, sort_keys=False, allow_unicode=True)
    print(f"Generated editable session plan ({len(plan['segments'])} segments, {len(plan['markers'])} markers) -> {out_path}")
