#!/usr/bin/env python3
"""
Local Whisper Subtitle (.srt) & Transcript Generator (`auto_captions.py`)

Runs OpenAI Whisper locally on the isolated Microphone track (`*_voice.wav`) to produce:
  1. `*.srt` — Frame-accurate subtitles ready to upload to YouTube Studio or drop into DaVinci Resolve
  2. `*_transcript.json` — Timestamped segments so you can search your recording by spoken words
"""

import argparse
import json
import os
import whisper


def fmt_srt_time(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    total_sec = int(seconds)
    m, s = divmod(total_sec, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_captions(audio_path: str, model_name: str = "base"):
    print(f"Loading Whisper model '{model_name}'...")
    model = whisper.load_model(model_name)

    print(f"Transcribing '{audio_path}'...")
    result = model.transcribe(audio_path, verbose=False)
    segments = result.get("segments", [])

    base = os.path.splitext(audio_path)[0]
    srt_path = f"{base}.srt"
    json_path = f"{base}_transcript.json"

    with open(srt_path, "w", encoding="utf-8") as srt_file:
        for idx, seg in enumerate(segments, 1):
            start_ts = fmt_srt_time(seg["start"])
            end_ts = fmt_srt_time(seg["end"])
            text = seg["text"].strip()
            srt_file.write(f"{idx}\n{start_ts} --> {end_ts}\n{text}\n\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(result, json_file, indent=2, ensure_ascii=False)

    print(f"Saved subtitles -> {srt_path}")
    print(f"Saved full transcript -> {json_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate .srt subtitles and JSON transcript from isolated voice WAV")
    parser.add_argument("--voice", required=True, help="Path to isolated *_voice.wav")
    parser.add_argument("--model", default="base", help="Whisper model size (tiny, base, small, medium, large)")
    args = parser.parse_args()
    generate_captions(args.voice, args.model)
