#!/usr/bin/env python3
"""
Privacy & Secret Window Auditor (`audit_privacy.py`)

Scans a session's `*_telemetry.jsonl` sidecar for any timestamps where a potentially
sensitive window title (e.g., password managers, .env files, email, private chats,
cloud consoles, SSH keys) was focused during recording.

Run this BEFORE editing or uploading to guarantee no accidental OPSEC leaks.
"""

import argparse
import json
import sys

DEFAULT_PATTERNS = [
    ".env",
    "secret",
    "password",
    "1password",
    "bitwarden",
    "keepass",
    "gmail",
    "inbox",
    "discord",
    "slack",
    "messages",
    "whatsapp",
    "signal",
    "bank",
    "aws management",
    "credentials",
    "id_ed25519",
    "id_rsa",
    "token",
]


def fmt_time(ms: int) -> str:
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def audit_telemetry(jsonl_path: str, extra_patterns=None):
    patterns = [p.lower() for p in DEFAULT_PATTERNS + (extra_patterns or [])]
    alerts = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            event = json.loads(line)
            win = event.get("window") or {}
            title = win.get("title") or ""
            title_lower = title.lower()

            matched = [p for p in patterns if p in title_lower]
            if matched:
                t_ms = event.get("t_ms", 0)
                if alerts and alerts[-1]["title"] == title and (t_ms - alerts[-1]["end_ms"]) <= 1500:
                    alerts[-1]["end_ms"] = t_ms
                else:
                    alerts.append({
                        "start_ms": t_ms,
                        "end_ms": t_ms,
                        "title": title,
                        "matched": matched,
                        "rect": win.get("rect"),
                    })

    if not alerts:
        print("✅ Privacy Audit PASSED: No sensitive window titles detected in telemetry.")
        return 0

    print(f"⚠️  Privacy Audit WARNING: Found {len(alerts)} sensitive window interval(s):")
    for idx, a in enumerate(alerts, 1):
        start_str = fmt_time(a["start_ms"])
        end_str = fmt_time(a["end_ms"])
        print(f"  {idx}. [{start_str} -> {end_str}] Window: '{a['title']}' (matched: {', '.join(a['matched'])})")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit recording telemetry for accidental secret/private windows")
    parser.add_argument("--telemetry", required=True, help="Path to *_telemetry.jsonl")
    parser.add_argument("--block", nargs="*", default=[], help="Additional keywords to flag (e.g. personal names)")
    args = parser.parse_args()
    sys.exit(audit_telemetry(args.telemetry, args.block))
