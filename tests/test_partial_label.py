"""Zichtbaar label gevraagd maar niet gelukt (geen ffmpeg, overlay faalt):
nooit een kale OK, wel een status per laag en een gerichte herhaalpoging.

Draaien:  .venv/bin/python -m unittest discover tests
"""

import queue
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
from PIL import Image  # noqa: E402

VIDEO = b"\x00\x00\x00\x18ftypmp42" + b"v" * 4000


def fake_sign(src, dst, manifest_path):
    Path(dst).write_bytes(b"C2PA" + Path(src).read_bytes())
    return True, ""


def fake_overlay(src, dst, settings):
    Path(dst).write_bytes(b"LABEL" + Path(src).read_bytes())
    return True, ""


class PartialLabelTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="c2pa_test_"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.inp = self.dir / "in"
        self.clip = self.inp / "a" / "clip.mp4"
        self.clip.parent.mkdir(parents=True)
        self.clip.write_bytes(VIDEO)
        self.out = self.inp / "gelabeld"
        self.ffmpeg = True
        self.overlay = fake_overlay
        for target, value in (
            ("sign_with_c2patool", fake_sign),
            ("verify_with_c2patool", lambda path, dst: (True, "")),
            ("burn_label", lambda im, settings: im.copy()),
            ("ffmpeg_present", lambda: self.ffmpeg),
            ("overlay_video_ffmpeg", lambda *a: self.overlay(*a)),
            ("c2patool_info", lambda: {"present": True}),
        ):
            p = mock.patch.object(app, target, side_effect=value)
            p.start()
            self.addCleanup(p.stop)

    def collect(self, job_id):
        self.addCleanup(app.RETRIES.pop, job_id, None)
        q = app.JOBS[job_id]["queue"]
        events = []
        while not q.empty():
            events.append(q.get())
        app.JOBS.pop(job_id, None)  # zoals api_stream na "done"
        logs = [e for e in events if e["type"] == "log"]
        summary = next(e for e in events if e["type"] == "summary")
        return logs, summary

    def run_batch(self, **cfg):
        job_id = uuid.uuid4().hex
        app.JOBS[job_id] = {"queue": queue.Queue(), "done": False}
        self.addCleanup(app.JOBS.pop, job_id, None)
        base = {
            "input_dir": str(self.inp), "recursive": True, "bronsoort": "volledig",
            "ai_tool": "Test", "burn_icon": True, "verify": True, "label": {},
        }
        base.update(cfg)
        app.process_batch(job_id, base)
        return (job_id,) + self.collect(job_id)

    def retry(self, job_id, payload=None):
        new_id = app.api_retry(job_id, payload)["job_id"]
        self.addCleanup(app.JOBS.pop, new_id, None)
        app.JOBS[new_id]["thread"].join(10)
        return self.collect(new_id)

    @staticmethod
    def steps(log):
        return [(s["name"], s["ok"]) for s in log["steps"]]

    def test_no_ffmpeg_is_partial_not_ok(self):
        self.ffmpeg = False
        _, logs, summary = self.run_batch()
        self.assertEqual([e["status"] for e in logs], ["DEELS"])
        self.assertIn("geen ffmpeg", logs[0]["msg"])
        self.assertEqual(self.steps(logs[0]), [("icoon", False), ("C2PA", True), ("verificatie", True)])
        self.assertEqual((summary["signed"], summary["partial"], summary["retry"]), (0, 1, 1))
        self.assertEqual((self.out / "a" / "clip.mp4").read_bytes(), b"C2PA" + VIDEO)

    def test_overlay_failure_is_partial_with_reason(self):
        self.overlay = lambda src, dst, s: (False, "onbekende codec")
        _, logs, summary = self.run_batch()
        self.assertEqual([e["status"] for e in logs], ["DEELS"])
        self.assertIn("onbekende codec", logs[0]["msg"])
        self.assertEqual(summary["partial"], 1)

    def test_label_not_requested_stays_ok(self):
        self.ffmpeg = False
        _, logs, summary = self.run_batch(burn_icon=False)
        self.assertEqual([e["status"] for e in logs], ["OK"])
        self.assertEqual(self.steps(logs[0]), [("C2PA", True), ("verificatie", True)])
        self.assertEqual((summary["signed"], summary["retry"]), (1, 0))

    def test_image_ok_next_to_partial_video(self):
        Image.new("RGB", (8, 8), "red").save(self.inp / "a" / "foto.jpg")
        self.ffmpeg = False
        _, logs, summary = self.run_batch()
        status = {e["file"]: e["status"] for e in logs}
        self.assertEqual(status, {str(Path("a/clip.mp4")): "DEELS", str(Path("a/foto.jpg")): "OK"})
        self.assertEqual((summary["signed"], summary["partial"], summary["retry"]), (1, 1, 1))

    def test_replace_mode_keeps_original(self):
        self.ffmpeg = False
        _, logs, summary = self.run_batch(replace_originals=True)
        self.assertEqual([e["status"] for e in logs], ["FOUT"])
        self.assertIn("origineel niet vervangen", logs[0]["msg"])
        self.assertEqual(self.steps(logs[0]), [("icoon", False)])
        self.assertEqual(self.clip.read_bytes(), VIDEO)
        self.assertEqual(sorted(p.name for p in self.clip.parent.iterdir()), ["clip.mp4"])
        self.assertEqual(summary["retry"], 1)

    def test_retry_redoes_only_failed_files_into_same_output(self):
        Image.new("RGB", (8, 8), "red").save(self.inp / "a" / "foto.jpg")
        self.ffmpeg = False
        job_id, _, _ = self.run_batch()
        foto_out = self.out / "a" / "foto.jpg"
        foto_before = foto_out.read_bytes()

        self.ffmpeg = True  # ffmpeg intussen geïnstalleerd
        logs, summary = self.retry(job_id)
        self.assertEqual([(e["status"], e["file"]) for e in logs], [("OK", str(Path("a/clip.mp4")))])
        self.assertEqual((self.out / "a" / "clip.mp4").read_bytes(), b"C2PA" + b"LABEL" + VIDEO)
        self.assertEqual(foto_out.read_bytes(), foto_before)
        self.assertEqual(summary["retry"], 0)

    def test_retry_in_replace_mode_needs_confirmation(self):
        self.ffmpeg = False
        job_id, _, _ = self.run_batch(replace_originals=True)
        with self.assertRaises(app.HTTPException):
            app.api_retry(job_id, {})

        self.ffmpeg = True
        logs, _ = self.retry(job_id, {"confirm_replace": True})
        self.assertEqual([e["status"] for e in logs], ["OK"])
        self.assertEqual(self.clip.read_bytes(), b"C2PA" + b"LABEL" + VIDEO)

    def test_nothing_to_retry(self):
        job_id, _, _ = self.run_batch(burn_icon=False)
        with self.assertRaises(app.HTTPException):
            app.api_retry(job_id, {})


if __name__ == "__main__":
    unittest.main()
