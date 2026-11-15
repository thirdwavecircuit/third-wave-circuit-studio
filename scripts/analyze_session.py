#!/usr/bin/env python3
"""
Session Analyzer, Master-Clock Aligner & Edit Plan Generator (`analyze_session.py`)

Reads the isolated microphone track (`*_voice.wav`) and 10Hz telemetry sidecar (`*_telemetry.jsonl`)
from a recording session, aligns both to the shared `OBS_FILE_START` master clock (`t_ms = 0`),
and produces:
  1. An enriched 10Hz timeline (`*_enriched_telemetry.jsonl`) where every 100ms tick includes
     `is_speaking`, `voice_db`, `active_monitor`, `cursor_monitor`, `is_active_input`, `cursor`, and `window`.
  2. A declarative `*_edit_plan.yaml` file with segment-level post-processing metadata:
       - Spoken segments (`voice_active: true`, suggested `speed: 1.0`)
       - Silent coding/drawing stretches (`voice_active: false`, suggested `speed: 8.0` timelapse)
       - Dominant active monitor (`1` or `2`), window title, and pixel bounding box (`x, y, w, h`)
       - Input activity (`is_active_input`, `click_count`)
       - Offline avatar composition config (`avatar_overlay: {enabled, position, scale}`)
       - F9 (HIGHLIGHT) & F10 (SECTION) markers pressed during recording
"""

import argparse
import json
import math
import os
import struct
import wave
from collections import Counter
import yaml


def analyze_wav_activity_with_db(wav_path: str, window_sec: float = 0.5, silence_db: float = -38.0):
    """Returns `(activity_bools, db_levels, window_sec)` per `window_sec` chunk."""
    with wave.open(wav_path, "rb") as wf:
        rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        frames_per_chunk = int(rate * window_sec)

        activity = []
        db_levels = []
        while True:
            raw = wf.readframes(frames_per_chunk)
            if not raw:
                break
            if sampwidth == 2:
                samples = struct.unpack(f"<{len(raw) // 2}h", raw)
                if not samples:
                    break
                rms = math.sqrt(sum(s * s for s in samples) / len(samples))
                db = round(20 * math.log10(max(rms, 1.0) / 32768.0), 1)
                db_levels.append(db)
                activity.append(db > silence_db)
            else:
                db_levels.append(-20.0)
                activity.append(True)
    return activity, db_levels, window_sec


def analyze_wav_activity(wav_path: str, window_sec: float = 0.5, silence_db: float = -38.0):
    """Backwards-compatible wrapper returning `(activity_bools, window_sec)`."""
    activity, _, step = analyze_wav_activity_with_db(wav_path, window_sec, silence_db)
    return activity, step


def load_telemetry(jsonl_path: str):
    events = []
    if not jsonl_path or not os.path.exists(jsonl_path):
        return events
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    # Align telemetry t_ms=0 with the moment OBS created the video file on disk
    obs_offset_ms = 0
    for e in events:
        m = str(e.get("marker") or "")
        if m.startswith("OBS_FILE_START:"):
            obs_offset_ms = e.get("t_ms", 0)
            break
    if obs_offset_ms > 0:
        for e in events:
            e["t_ms"] = max(0, e.get("t_ms", 0) - obs_offset_ms)
    return events


def enrich_telemetry_with_voice(events: list, activity: list, db_levels: list, step_sec: float) -> list:
    """Attaches `is_speaking` and `voice_db` to each 10Hz telemetry tick based on aligned `t_ms`."""
    enriched = []
    step_ms = max(1, int(step_sec * 1000))
    for e in events:
        ev = dict(e)
        idx = min(len(activity) - 1, max(0, int(ev.get("t_ms", 0)) // step_ms)) if activity else -1
        ev["is_speaking"] = bool(activity[idx]) if idx >= 0 else False
        ev["voice_db"] = float(db_levels[idx]) if idx >= 0 else -96.0
        enriched.append(ev)
    return enriched


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_edit_plan(
    wav_path: str,
    telemetry_path: str = None,
    min_silence_sec: float = 3.0,
    enriched_telemetry_out: str = None,
):
    activity, db_levels, step = analyze_wav_activity_with_db(wav_path)
    raw_telemetry = load_telemetry(telemetry_path)
    telemetry = enrich_telemetry_with_voice(raw_telemetry, activity, db_levels, step)

    if enriched_telemetry_out and telemetry:
        with open(enriched_telemetry_out, "w", encoding="utf-8") as ef:
            for ev in telemetry:
                ef.write(json.dumps(ev) + "\n")

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

        # Find bounding box of dominant window for optional post-crop
        dominant_rect = None
        for e in seg_events:
            w_info = e.get("window") or {}
            if w_info.get("title") == dominant_window and w_info.get("rect"):
                dominant_rect = w_info["rect"]
                break

        monitors = [e.get("active_monitor") for e in seg_events if e.get("active_monitor") is not None]
        dominant_monitor = Counter(monitors).most_common(1)[0][0] if monitors else 1

        active_inputs = [bool(e.get("is_active_input")) for e in seg_events if "is_active_input" in e]
        is_active_input = any(active_inputs) if active_inputs else True

        clicks = sum(
            1 for e in seg_events
            if (e.get("cursor") or {}).get("lmb") or (e.get("cursor") or {}).get("rmb")
        )

        seg_markers = [e["marker"] for e in seg_events if e.get("marker")]

        plan_segments.append({
            "id": i + 1,
            "start": fmt_time(seg["start_sec"]),
            "end": fmt_time(seg["end_sec"]),
            "duration_sec": round(seg["end_sec"] - seg["start_sec"], 1),
            "voice_active": seg["voice_active"],
            "active_monitor": dominant_monitor,
            "is_active_input": is_active_input,
            "click_ticks": clicks,
            "dominant_window": dominant_window,
            "dominant_window_rect": dominant_rect,
            "markers": seg_markers,
            "action": "keep" if seg["voice_active"] else "timelapse",
            "speed": 1.0 if seg["voice_active"] else 8.0,
            "view_mode": "full_screen",  # Options: full_screen | active_window | cursor_zoom
            "show_avatar": seg["voice_active"],
            "avatar_overlay": {
                "enabled": seg["voice_active"],
                "position": "bottom-right",
                "scale": 0.28,
            },
        })

    return {
        "source_voice": os.path.basename(wav_path),
        "source_telemetry": os.path.basename(telemetry_path) if telemetry_path else None,
        "enriched_telemetry": os.path.basename(enriched_telemetry_out) if enriched_telemetry_out else None,
        "markers": markers_summary,
        "segments": plan_segments,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Align isolated voice WAV + 10Hz telemetry onto a master clock and generate an editable YAML plan"
    )
    parser.add_argument("--voice", required=True, help="Path to isolated *_voice.wav (Track 2)")
    parser.add_argument("--telemetry", help="Path to *_telemetry.jsonl")
    parser.add_argument("--out", help="Output YAML path (defaults to *_edit_plan.yaml)")
    parser.add_argument(
        "--enriched-out",
        help="Output path for enriched 10Hz JSONL with is_speaking merged (defaults to *_enriched_telemetry.jsonl)",
    )
    args = parser.parse_args()

    out_path = args.out or args.voice.replace("_voice.wav", "_edit_plan.yaml")
    enriched_path = args.enriched_out
    if not enriched_path and args.telemetry:
        enriched_path = args.telemetry.replace("_telemetry.jsonl", "_enriched_telemetry.jsonl")

    plan = build_edit_plan(args.voice, args.telemetry, enriched_telemetry_out=enriched_path)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(plan, f, sort_keys=False, allow_unicode=True)
    print(f"Generated editable session plan ({len(plan['segments'])} segments, {len(plan['markers'])} markers) -> {out_path}")
    if enriched_path and os.path.exists(enriched_path):
        print(f"Generated master-clock enriched 10Hz telemetry -> {enriched_path}")
