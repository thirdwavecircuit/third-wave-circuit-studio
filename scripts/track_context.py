#!/usr/bin/env python3
"""
Synchronized Window, Monitor & Cursor Telemetry Logger (`track_context.py`)

Runs alongside OBS recordings to log a 10Hz JSONL sidecar (`*_telemetry.jsonl`) containing:
  - Exact timestamp (ms since start + wall-clock ISO timestamp)
  - Mouse cursor coordinates (x, y)
  - Active/focused window bounding box (left, top, width, height)
  - Active window title & process ID

Why this matters:
  Instead of having to crop to a single window/tab BEFORE recording (and losing context when you
  alt-tab), you record your full display(s) and use this sidecar data later to:
  1. Auto-crop or smoothly zoom into the active window/tab or cursor position (Screen Studio style)
  2. Automatically switch between Monitor 1 and Monitor 2 based on where your cursor/focus is
  3. Auto-detect or blur timestamps where sensitive window titles (e.g. .env, passwords, messages) appear
"""

import argparse
import ctypes
from ctypes import wintypes
import datetime
import json
import time


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


user32 = ctypes.windll.user32


def get_cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def get_active_window_info():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    bounds = {
        "x": rect.left,
        "y": rect.top,
        "w": max(0, rect.right - rect.left),
        "h": max(0, rect.bottom - rect.top),
    }

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    return {
        "hwnd": int(hwnd),
        "pid": int(pid.value),
        "title": title,
        "rect": bounds,
    }


def record_telemetry(output_path: str, hz: float = 10.0):
    interval = 1.0 / hz
    start_monotonic = time.monotonic()
    print(f"Recording window & cursor telemetry ({hz} Hz) -> {output_path}")
    print("Press Ctrl+C to stop.")

    with open(output_path, "w", encoding="utf-8") as f:
        try:
            while True:
                now_mono = time.monotonic()
                elapsed_ms = int((now_mono - start_monotonic) * 1000)
                cx, cy = get_cursor_pos()
                win = get_active_window_info()

                event = {
                    "t_ms": elapsed_ms,
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "cursor": {"x": cx, "y": cy},
                    "window": win,
                }
                f.write(json.dumps(event) + "\n")
                f.flush()

                sleep_time = interval - (time.monotonic() - now_mono)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            print(f"\nSaved telemetry log to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log active window bounds & cursor coordinates for video post-processing")
    parser.add_argument(
        "--out",
        default=f"session_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_telemetry.jsonl",
        help="Output .jsonl path",
    )
    parser.add_argument("--hz", type=float, default=10.0, help="Sampling rate in Hz (default: 10)")
    args = parser.parse_args()
    record_telemetry(args.out, args.hz)
