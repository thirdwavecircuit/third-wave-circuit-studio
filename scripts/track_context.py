#!/usr/bin/env python3
"""
Synchronized Window, Cursor & Highlight Marker Telemetry Logger (`track_context.py`)

Runs alongside OBS recordings to log a 10Hz JSONL sidecar (`*_telemetry.jsonl`) containing:
  - Exact timestamp (`t_ms` since start + wall-clock UTC ISO timestamp)
  - Mouse cursor coordinates (`x`, `y`) & click state (`left_click`, `right_click`)
  - Active/focused window bounding box (`x`, `y`, `w`, `h`) & window title
  - Global Hotkey Markers:
      * F9  -> Logs a "HIGHLIGHT" marker (great take, cool bug, key moment)
      * F10 -> Logs a "SECTION" marker (new step / chapter transition)
"""

import argparse
import ctypes
from ctypes import wintypes
import datetime
import json
import os
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


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


user32 = getattr(ctypes, "windll", None).user32 if hasattr(ctypes, "windll") else None
kernel32 = getattr(ctypes, "windll", None).kernel32 if hasattr(ctypes, "windll") else None

# Windows Virtual Key Codes
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_F9 = 0x78
VK_F10 = 0x79


def is_key_down(vk_code: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk_code) & 0x8000)


def get_cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def get_idle_ms() -> int:
    """Return milliseconds since last keyboard or mouse input (privacy-safe activity signal)."""
    if not user32 or not kernel32:
        return 0
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if user32.GetLastInputInfo(ctypes.byref(lii)):
        tick = kernel32.GetTickCount()
        return max(0, int((tick - lii.dwTime) & 0xFFFFFFFF))
    return 0


def infer_monitor_index(x: int, y: int) -> int:
    """Return 1 for primary monitor (0..primary_w), 2 for secondary monitor."""
    if not user32:
        return 1
    primary_w = user32.GetSystemMetrics(0)
    primary_h = user32.GetSystemMetrics(1)
    if 0 <= x < primary_w and 0 <= y < primary_h:
        return 1
    return 2


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
    print(f"Recording window, cursor & marker telemetry ({hz} Hz) -> {output_path}")
    print("Hotkeys active while recording:")
    print("  [F9]  -> Drop a HIGHLIGHT marker")
    print("  [F10] -> Drop a SECTION / CHAPTER marker")
    print("Press Ctrl+C to stop.")

    f9_was_down = False
    f10_was_down = False
    watch_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    existing_media = set(
        fn for fn in os.listdir(watch_dir)
        if fn.endswith((".mp4", ".mkv", ".mov"))
    )
    synced_media_file = None

    with open(output_path, "w", encoding="utf-8") as f:
        try:
            while True:
                now_mono = time.monotonic()
                elapsed_ms = int((now_mono - start_monotonic) * 1000)
                cx, cy = get_cursor_pos()
                win = get_active_window_info()

                f9_down = is_key_down(VK_F9)
                f10_down = is_key_down(VK_F10)

                marker = None
                if synced_media_file is None:
                    try:
                        current_media = set(
                            fn for fn in os.listdir(watch_dir)
                            if fn.endswith((".mp4", ".mkv", ".mov"))
                        )
                        new_files = current_media - existing_media
                        if new_files:
                            synced_media_file = sorted(new_files)[-1]
                            marker = f"OBS_FILE_START:{synced_media_file}"
                            print(f"  [SYNC] [{elapsed_ms / 1000:.2f}s] Locked sync to OBS file: {synced_media_file}")
                    except Exception:
                        pass

                if f9_down and not f9_was_down:
                    marker = "HIGHLIGHT"
                    print(f"  [HIGHLIGHT] [{elapsed_ms / 1000:.1f}s] Marked HIGHLIGHT (F9)")
                elif f10_down and not f10_was_down:
                    marker = "SECTION"
                    print(f"  [SECTION] [{elapsed_ms / 1000:.1f}s] Marked SECTION (F10)")

                f9_was_down = f9_down
                f10_was_down = f10_down

                idle_ms = get_idle_ms()
                win_mon = None
                if win and "rect" in win:
                    wx = win["rect"]["x"] + (win["rect"]["w"] // 2)
                    wy = win["rect"]["y"] + (win["rect"]["h"] // 2)
                    win_mon = infer_monitor_index(wx, wy)

                event = {
                    "t_ms": elapsed_ms,
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "active_monitor": win_mon or infer_monitor_index(cx, cy),
                    "cursor_monitor": infer_monitor_index(cx, cy),
                    "is_active_input": idle_ms <= 250,
                    "idle_ms": idle_ms,
                    "cursor": {
                        "x": cx,
                        "y": cy,
                        "lmb": is_key_down(VK_LBUTTON),
                        "rmb": is_key_down(VK_RBUTTON),
                    },
                    "window": win,
                    "marker": marker,
                }
                f.write(json.dumps(event) + "\n")
                f.flush()

                sleep_time = interval - (time.monotonic() - now_mono)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            print(f"\nSaved telemetry log to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Log active window bounds, cursor & F9/F10 markers")
    parser.add_argument(
        "--out",
        default=f"session_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_telemetry.jsonl",
        help="Output .jsonl path",
    )
    parser.add_argument("--hz", type=float, default=10.0, help="Sampling rate in Hz (default: 10)")
    args = parser.parse_args()
    record_telemetry(args.out, args.hz)
