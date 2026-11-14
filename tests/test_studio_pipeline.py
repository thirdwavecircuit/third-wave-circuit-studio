import json
import math
import os
import struct
import sys
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "youtube-gitops"))

import analyze_session
import audit_privacy
import auto_captions
import configure_studio
import render_roughcut
import sync_video


def create_synthetic_wav(path: Path, sample_rate: int = 16000, segments=((1.0, True), (4.0, False), (1.5, True))):
    """Writes a 16-bit mono WAV file with alternating loud (speech) and silent segments."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        for duration_sec, is_loud in segments:
            num_samples = int(sample_rate * duration_sec)
            samples = []
            for i in range(num_samples):
                if is_loud:
                    val = int(12000 * math.sin(2 * math.pi * 440 * (i / sample_rate)))
                else:
                    val = 0
                samples.append(val)
            wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))


class TestStudioPipeline(unittest.TestCase):
    def test_build_scenes_single_and_dual_monitors(self):
        single = [{"index": 0, "device": "D1", "primary": True, "width": 1920, "height": 1080}]
        scenes_1 = configure_studio.build_scenes_json("TestProf", single)
        self.assertEqual(len(scenes_1["scene_order"]), 1)
        self.assertEqual(scenes_1["DesktopAudioDevice1"]["mixers"], 5)  # Track 1 + Track 3
        self.assertEqual(scenes_1["AuxAudioDevice1"]["mixers"], 3)      # Track 1 + Track 2
        self.assertEqual(len(scenes_1["AuxAudioDevice1"]["filters"]), 3)

        dual = [
            {"index": 0, "device": "D1", "primary": True, "width": 1920, "height": 1080},
            {"index": 1, "device": "D2", "primary": False, "width": 2560, "height": 1440},
        ]
        scenes_2 = configure_studio.build_scenes_json("TestProf", dual)
        self.assertEqual(len(scenes_2["scene_order"]), 3)
        self.assertIn("ISO: Dual Monitors (Display 1 + Display 2)", [s["name"] for s in scenes_2["scene_order"]])

    def test_bootstrap_studio_writes_all_obs_configs(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_obs_root = tmp_path / "obs-studio"
            fake_out_dir = tmp_path / "recordings"

            with patch.object(configure_studio, "get_obs_config_root", return_value=fake_obs_root), \
                 patch.object(configure_studio, "detect_gpu_encoder", return_value="jim_nvenc"), \
                 patch.object(configure_studio, "detect_displays", return_value=[
                     {"index": 0, "device": "D1", "primary": True, "width": 1920, "height": 1080}
                 ]):
                configure_studio.bootstrap_studio("UnitTestProfile", fake_out_dir, 3840, 1080, 60, 18)

            self.assertTrue((fake_obs_root / "global.ini").exists())
            basic_ini = (fake_obs_root / "basic" / "profiles" / "UnitTestProfile" / "basic.ini").read_text()
            self.assertIn("RecFormat2=hybrid_mp4", basic_ini)
            self.assertIn("RecEncoder=jim_nvenc", basic_ini)
            self.assertIn("BaseCX=3840", basic_ini)

            enc_json = json.loads(
                (fake_obs_root / "basic" / "profiles" / "UnitTestProfile" / "recordEncoder.json").read_text()
            )
            self.assertEqual(enc_json["cqp"], 18)

    def test_telemetry_obs_file_start_offset_alignment(self):
        with TemporaryDirectory() as tmp:
            jsonl = Path(tmp) / "test_telemetry.jsonl"
            events = [
                {"t_ms": 500, "window": {"title": "Pre-OBS"}, "marker": None},
                {"t_ms": 1500, "window": {"title": "Blender"}, "marker": "OBS_FILE_START:2026-11-14.mp4"},
                {"t_ms": 2500, "window": {"title": "Blender"}, "marker": "HIGHLIGHT"},
            ]
            jsonl.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

            loaded = analyze_session.load_telemetry(str(jsonl))
            self.assertEqual(loaded[0]["t_ms"], 0)
            self.assertEqual(loaded[1]["t_ms"], 0)
            self.assertEqual(loaded[2]["t_ms"], 1000)

    def test_analyze_session_voice_and_silence_segmentation(self):
        with TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "session_voice.wav"
            tel_path = Path(tmp) / "session_telemetry.jsonl"

            # 1.5s speech -> 4.0s silence -> 1.5s speech
            create_synthetic_wav(wav_path, segments=((1.5, True), (4.0, False), (1.5, True)))

            events = [
                {"t_ms": 500, "window": {"title": "VS Code"}, "marker": "HIGHLIGHT"},
                {"t_ms": 3000, "window": {"title": "Blender"}, "marker": None},
                {"t_ms": 6000, "window": {"title": "VS Code"}, "marker": "SECTION"},
            ]
            tel_path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

            plan = analyze_session.build_edit_plan(str(wav_path), str(tel_path), min_silence_sec=3.0)
            self.assertEqual(len(plan["segments"]), 3)

            # Segment 1: Speech
            self.assertTrue(plan["segments"][0]["voice_active"])
            self.assertEqual(plan["segments"][0]["action"], "keep")
            self.assertEqual(plan["segments"][0]["speed"], 1.0)
            self.assertEqual(plan["segments"][0]["dominant_window"], "VS Code")

            # Segment 2: Silent drawing/coding -> Timelapse
            self.assertFalse(plan["segments"][1]["voice_active"])
            self.assertEqual(plan["segments"][1]["action"], "timelapse")
            self.assertEqual(plan["segments"][1]["speed"], 8.0)
            self.assertEqual(plan["segments"][1]["dominant_window"], "Blender")

            # Segment 3: Speech
            self.assertTrue(plan["segments"][2]["voice_active"])
            self.assertEqual(plan["segments"][2]["action"], "keep")

    def test_audit_privacy_detects_sensitive_windows(self):
        with TemporaryDirectory() as tmp:
            clean_path = Path(tmp) / "clean.jsonl"
            clean_path.write_text(
                json.dumps({"t_ms": 100, "window": {"title": "Blender - avatar.blend"}}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(audit_privacy.audit_telemetry(str(clean_path)), 0)

            leak_path = Path(tmp) / "leak.jsonl"
            leak_events = [
                {"t_ms": 1000, "window": {"title": "1Password - Vault"}},
                {"t_ms": 1200, "window": {"title": "1Password - Vault"}},
                {"t_ms": 5000, "window": {"title": "vim .env.production"}},
            ]
            leak_path.write_text("\n".join(json.dumps(e) for e in leak_events), encoding="utf-8")
            self.assertEqual(audit_privacy.audit_telemetry(str(leak_path)), 1)

    def test_srt_formatting_and_rollover_edge_case(self):
        self.assertEqual(auto_captions.fmt_srt_time(0.0), "00:00:00,000")
        self.assertEqual(auto_captions.fmt_srt_time(65.432), "00:01:05,432")
        self.assertEqual(auto_captions.fmt_srt_time(1.9999), "00:00:02,000")

    def test_render_time_parser_and_youtube_description(self):
        self.assertEqual(render_roughcut.parse_time_sec("01:02:03"), 3723.0)
        self.assertEqual(render_roughcut.parse_time_sec("02:30"), 150.0)

        manifest = {
            "description_body": "Hello world",
            "chapters": [
                {"time": "00:00", "title": "Intro"},
                {"time": "02:15", "title": "Build"},
            ],
        }
        desc = sync_video.render_description(manifest)
        self.assertIn("Hello world", desc)
        self.assertIn("00:00 Intro", desc)
        self.assertIn("02:15 Build", desc)


if __name__ == "__main__":
    unittest.main()
