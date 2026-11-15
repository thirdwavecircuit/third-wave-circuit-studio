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
sys.path.insert(0, str(REPO_ROOT / "recording"))
sys.path.insert(0, str(REPO_ROOT / "post-processing"))
sys.path.insert(0, str(REPO_ROOT / "devops"))
sys.path.insert(0, str(REPO_ROOT / "youtube-gitops"))

import analyze_session
import audit_privacy
import auto_captions
import configure_studio
import recompile_streams
import render_roughcut
import sync_drive_recordings
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
        single = [{
            "index": 0,
            "device": "D1",
            "monitor_id": "\\\\?\\DISPLAY#TEST#123",
            "primary": True,
            "width": 1920,
            "height": 1080,
        }]
        scenes_1 = configure_studio.build_scenes_json("TestProf", single)
        self.assertEqual(len(scenes_1["scene_order"]), 1)
        self.assertEqual(scenes_1["DesktopAudioDevice1"]["mixers"], 5)  # Track 1 + Track 3
        self.assertEqual(scenes_1["AuxAudioDevice1"]["mixers"], 3)      # Track 1 + Track 2
        self.assertEqual(len(scenes_1["AuxAudioDevice1"]["filters"]), 3)
        mon_src = [s for s in scenes_1["sources"] if s["id"] == "monitor_capture"][0]
        self.assertEqual(mon_src["settings"]["monitor_id"], "\\\\?\\DISPLAY#TEST#123")

        dual = [
            {"index": 0, "device": "D1", "primary": True, "width": 1920, "height": 1080},
            {"index": 1, "device": "D2", "primary": False, "width": 2560, "height": 1440},
        ]
        scenes_2 = configure_studio.build_scenes_json("TestProf", dual)
        self.assertEqual(len(scenes_2["scene_order"]), 3)
        self.assertEqual(scenes_2["current_scene"], "ISO: Display 2 (2560x1440) + Camera")
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
                {
                    "t_ms": 500,
                    "active_monitor": 2,
                    "is_active_input": True,
                    "cursor": {"x": 2200, "y": 400, "lmb": True, "rmb": False},
                    "window": {"title": "VS Code", "rect": {"x": 1920, "y": 0, "w": 1600, "h": 1000}},
                    "marker": "HIGHLIGHT",
                },
                {
                    "t_ms": 3000,
                    "active_monitor": 2,
                    "is_active_input": True,
                    "cursor": {"x": 2400, "y": 500, "lmb": False, "rmb": False},
                    "window": {"title": "Blender", "rect": {"x": 1920, "y": 0, "w": 2560, "h": 1440}},
                    "marker": None,
                },
                {
                    "t_ms": 6000,
                    "active_monitor": 1,
                    "is_active_input": False,
                    "cursor": {"x": 500, "y": 500, "lmb": False, "rmb": False},
                    "window": {"title": "VS Code", "rect": {"x": 0, "y": 0, "w": 1920, "h": 1080}},
                    "marker": "SECTION",
                },
            ]
            tel_path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
            enriched_path = Path(tmp) / "session_enriched_telemetry.jsonl"

            plan = analyze_session.build_edit_plan(
                str(wav_path),
                str(tel_path),
                min_silence_sec=3.0,
                enriched_telemetry_out=str(enriched_path),
            )
            self.assertEqual(len(plan["segments"]), 3)
            self.assertTrue(enriched_path.exists())
            enriched_rows = [json.loads(line) for line in enriched_path.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(enriched_rows[0]["is_speaking"])
            self.assertFalse(enriched_rows[1]["is_speaking"])

            # Segment 1: Speech
            self.assertTrue(plan["segments"][0]["voice_active"])
            self.assertEqual(plan["segments"][0]["active_monitor"], 2)
            self.assertTrue(plan["segments"][0]["is_active_input"])
            self.assertEqual(plan["segments"][0]["click_ticks"], 1)
            self.assertEqual(plan["segments"][0]["action"], "keep")
            self.assertEqual(plan["segments"][0]["speed"], 1.0)
            self.assertEqual(plan["segments"][0]["dominant_window"], "VS Code")
            self.assertEqual(plan["segments"][0]["dominant_window_rect"]["w"], 1600)
            self.assertTrue(plan["segments"][0]["avatar_overlay"]["enabled"])

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

        crop_str = render_roughcut.build_crop_filter({"x": 100, "y": 50, "w": 1281, "h": 721})
        self.assertEqual(crop_str, "crop=1280:720:100:50")
        ox, oy = render_roughcut.compute_overlay_xy("bottom-right", margin=32)
        self.assertIn("main_w-overlay_w-32", ox)

    def test_split_and_recompile_1x_sanity_check_workflow(self):
        """Regression test verifying split_streams.ps1 maps both video+audio and recompile_streams.py builds a valid 4-input 1x command."""
        split_ps1 = (REPO_ROOT / "recording" / "split_streams.ps1").read_text(encoding="utf-8")
        # Must explicitly map 0:v:0 alongside audio stream so video is never dropped
        self.assertIn("-map 0:v:0 -map 0:a:0", split_ps1)
        self.assertIn("-map 0:v:0 -map 0:a:1", split_ps1)

        cmd = recompile_streams.build_recompile_command(
            screen_mp4="test_screen.mp4",
            camera_mp4="test_camera.mp4",
            voice_wav="test_voice.wav",
            desktop_wav="test_desktop.wav",
            output_mp4="test_recompiled_1x.mp4",
            pip_width=538,
            margin=32,
            v_encoder=["-c:v", "libx264"],
        )
        # Verify all 4 inputs precede -filter_complex and output codecs
        i_indices = [idx for idx, token in enumerate(cmd) if token == "-i"]
        fc_index = cmd.index("-filter_complex")
        self.assertEqual(len(i_indices), 4)
        self.assertTrue(all(idx < fc_index for idx in i_indices))
        self.assertIn("amix=inputs=2", cmd[fc_index + 1])
        self.assertIn("overlay=main_w-overlay_w-32:main_h-overlay_h-32", cmd[fc_index + 1])

        # If ffmpeg is installed, run a full end-to-end synthetic 3840x1080 3-audio-track split + 1x recompile
        if recompile_streams.shutil.which("ffmpeg"):
            with TemporaryDirectory() as tmp:
                tmp_p = Path(tmp)
                raw_iso = tmp_p / "synth_iso.mp4"
                screen_out = tmp_p / "synth_iso_screen.mp4"
                camera_out = tmp_p / "synth_iso_camera.mp4"
                voice_out = tmp_p / "synth_iso_voice.wav"
                desktop_out = tmp_p / "synth_iso_desktop.wav"
                recompiled_out = tmp_p / "synth_iso_recompiled_1x.mp4"

                # 1. Generate synthetic 1s 3840x1080 video with 3 distinct audio tracks
                re_cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "color=c=blue:s=3840x1080:r=30:d=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
                    "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=1",
                    "-f", "lavfi", "-i", "sine=frequency=660:sample_rate=48000:duration=1",
                    "-map", "0:v:0", "-map", "1:a:0", "-map", "2:a:0", "-map", "3:a:0",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                    "-c:a", "aac",
                    str(raw_iso),
                ]
                recompile_streams.subprocess.run(re_cmd, check=True, stdout=recompile_streams.subprocess.DEVNULL, stderr=recompile_streams.subprocess.DEVNULL)

                # 2. Split into the 4 independent files (_screen, _camera, _voice, _desktop)
                for crop_expr, a_map, out_f in [
                    ("crop=1920:1080:0:0", "0:a:0", screen_out),
                    ("crop=1920:1080:1920:0", "0:a:1", camera_out),
                ]:
                    recompile_streams.subprocess.run(
                        [
                            "ffmpeg", "-y", "-i", str(raw_iso),
                            "-map", "0:v:0", "-map", a_map,
                            "-filter:v", crop_expr,
                            "-c:v", "libx264", "-preset", "ultrafast",
                            "-c:a", "aac", str(out_f),
                        ],
                        check=True,
                        stdout=recompile_streams.subprocess.DEVNULL,
                        stderr=recompile_streams.subprocess.DEVNULL,
                    )
                for a_map, out_w in [("0:a:1", voice_out), ("0:a:2", desktop_out)]:
                    recompile_streams.subprocess.run(
                        ["ffmpeg", "-y", "-i", str(raw_iso), "-map", a_map, "-c:a", "pcm_s16le", str(out_w)],
                        check=True,
                        stdout=recompile_streams.subprocess.DEVNULL,
                        stderr=recompile_streams.subprocess.DEVNULL,
                    )

                # 3. Recompile the 4 separated streams into a 1:1 (1x) combined MP4
                run_cmd = recompile_streams.build_recompile_command(
                    screen_mp4=str(screen_out),
                    camera_mp4=str(camera_out),
                    voice_wav=str(voice_out),
                    desktop_wav=str(desktop_out),
                    output_mp4=str(recompiled_out),
                    v_encoder=["-c:v", "libx264", "-preset", "ultrafast"],
                )
                recompile_streams.subprocess.run(run_cmd, check=True, stdout=recompile_streams.subprocess.DEVNULL, stderr=recompile_streams.subprocess.DEVNULL)
                self.assertTrue(recompiled_out.exists())
                self.assertGreater(recompiled_out.stat().st_size, 1000)

    def test_devops_drive_session_grouping_and_md5(self):
        self.assertEqual(
            sync_drive_recordings.infer_session_group("2026-11-15 15-12-06_screen.mp4"),
            "session_2026-11-15_15-12-06",
        )
        self.assertEqual(
            sync_drive_recordings.infer_session_group("session_2026-11-15_14-40-30_telemetry.jsonl"),
            "session_2026-11-15_14-40-30",
        )
        with TemporaryDirectory() as tmp:
            sample = Path(tmp) / "test.bin"
            sample.write_bytes(b"third-wave-circuit")
            self.assertEqual(len(sync_drive_recordings.compute_md5(sample)), 32)


if __name__ == "__main__":
    unittest.main()
