"""Vervang-modus: een fout bij het overschrijven mag nooit zowel het origineel
als de getekende versie kosten.

Draaien:  .venv/bin/python -m unittest discover tests
"""

import errno
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

ORIGINAL = b"origineel " * 50_000
SIGNED = b"getekend! " * 60_000
REAL_COPYFILE = shutil.copyfile


def no_rename():
    """os.replace zoals cloud-opslag hem weigert."""
    return mock.patch.object(
        app.os, "replace", side_effect=PermissionError(errno.EPERM, "Operation not permitted")
    )


def copy_fails_into(target: Path, times: int = 1, halfway: bool = True):
    """copyfile die naar `target` faalt: halverwege (half geschreven) of meteen."""
    left = [times]

    def copy(src, dst, *args, **kwargs):
        if Path(dst) == target and left[0] > 0:
            left[0] -= 1
            if halfway:
                data = Path(src).read_bytes()
                Path(dst).write_bytes(data[: len(data) // 2])
                raise OSError(errno.EIO, "Input/output error")
            raise PermissionError(errno.EACCES, "Permission denied")
        return REAL_COPYFILE(src, dst, *args, **kwargs)

    return mock.patch.object(app.shutil, "copyfile", side_effect=copy)


class ReplaceOriginalTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="c2pa_test_"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.original = self.dir / "foto.jpg"
        self.signed = self.dir / ".c2patmp_foto.jpg"
        self.backup = self.dir / ".c2pabackup_foto.jpg"
        self.original.write_bytes(ORIGINAL)
        self.signed.write_bytes(SIGNED)

    def replace(self):
        app.replace_original(self.signed, self.original, self.backup)

    def test_rename(self):
        self.replace()
        self.assertEqual(self.original.read_bytes(), SIGNED)
        self.assertFalse(self.signed.exists())
        self.assertFalse(self.backup.exists())

    def test_rename_refused_copy_ok(self):
        with no_rename():
            self.replace()
        self.assertEqual(self.original.read_bytes(), SIGNED)
        self.assertFalse(self.signed.exists())
        self.assertFalse(self.backup.exists())

    def test_copy_fails_halfway_restores_original(self):
        with no_rename(), copy_fails_into(self.original):
            with self.assertRaises(app.ReplaceFailed) as ctx:
                self.replace()
        self.assertIn("teruggezet", str(ctx.exception))
        self.assertEqual(self.original.read_bytes(), ORIGINAL)
        self.assertEqual(self.signed.read_bytes(), SIGNED)
        self.assertFalse(self.backup.exists())

    def test_copy_and_restore_fail_keep_backup_and_signed(self):
        with no_rename(), copy_fails_into(self.original, times=2):
            with self.assertRaises(app.ReplaceFailed) as ctx:
                self.replace()
        self.assertNotEqual(self.original.read_bytes(), ORIGINAL)  # beschadigd
        self.assertEqual(self.backup.read_bytes(), ORIGINAL)
        self.assertEqual(self.signed.read_bytes(), SIGNED)
        self.assertIn(str(self.backup), str(ctx.exception))
        self.assertIn(str(self.signed), str(ctx.exception))

    def test_copy_refused_before_writing(self):
        # bv. Windows met het bestand open in een ander programma
        with no_rename(), copy_fails_into(self.original, halfway=False):
            with self.assertRaises(app.ReplaceFailed) as ctx:
                self.replace()
        self.assertIn("ongewijzigd", str(ctx.exception))
        self.assertEqual(self.original.read_bytes(), ORIGINAL)
        self.assertEqual(self.signed.read_bytes(), SIGNED)
        self.assertFalse(self.backup.exists())

    def test_backup_fails_leaves_original_untouched(self):
        with no_rename(), copy_fails_into(self.backup):
            with self.assertRaises(app.ReplaceFailed):
                self.replace()
        self.assertEqual(self.original.read_bytes(), ORIGINAL)
        self.assertEqual(self.signed.read_bytes(), SIGNED)
        self.assertFalse(self.backup.exists())

    def test_existing_backup_is_never_overwritten(self):
        self.backup.write_bytes(b"eerdere backup")
        with no_rename():
            with self.assertRaises(app.ReplaceFailed):
                self.replace()
        self.assertEqual(self.backup.read_bytes(), b"eerdere backup")
        self.assertEqual(self.original.read_bytes(), ORIGINAL)
        self.assertEqual(self.signed.read_bytes(), SIGNED)


def fake_sign(src, dst, manifest_path):
    Path(dst).write_bytes(b"C2PA" + Path(src).read_bytes())
    return True, ""


class ProcessBatchReplaceTest(unittest.TestCase):
    """Dezelfde fouten via process_batch: de foutafhandeling daar mag de
    getekende versie niet alsnog opruimen."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="c2pa_test_"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.original = self.dir / "foto.jpg"
        self.signed = self.dir / ".c2patmp_foto.jpg"
        self.backup = self.dir / ".c2pabackup_foto.jpg"
        self.original.write_bytes(ORIGINAL)
        for target, value in (
            ("sign_with_c2patool", fake_sign),
            ("verify_with_c2patool", lambda path, dst: (True, "")),
        ):
            p = mock.patch.object(app, target, side_effect=value)
            p.start()
            self.addCleanup(p.stop)

    def run_batch(self):
        job_id = uuid.uuid4().hex
        app.JOBS[job_id] = {"queue": queue.Queue(), "done": False}
        self.addCleanup(app.JOBS.pop, job_id, None)
        cfg = {
            "input_dir": str(self.dir),
            "replace_originals": True,
            "bronsoort": "volledig",
            "ai_tool": "Test",
            "burn_icon": False,
            "verify": True,
        }
        app.process_batch(job_id, cfg)
        q = app.JOBS[job_id]["queue"]
        events = []
        while not q.empty():
            events.append(q.get())
        return [e for e in events if e["type"] == "log"]

    def test_rename_refused_copy_ok(self):
        with no_rename():
            logs = self.run_batch()
        self.assertEqual([e["status"] for e in logs], ["OK"])
        self.assertEqual(self.original.read_bytes(), b"C2PA" + ORIGINAL)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["foto.jpg"])

    def test_copy_and_restore_fail_then_next_run_skips(self):
        with no_rename(), copy_fails_into(self.original, times=2):
            logs = self.run_batch()
        self.assertEqual([e["status"] for e in logs], ["FOUT"])
        self.assertEqual(self.backup.read_bytes(), ORIGINAL)
        self.assertEqual(self.signed.read_bytes(), b"C2PA" + ORIGINAL)

        # Volgende run: het (beschadigde) origineel niet opnieuw backuppen.
        with no_rename():
            logs = self.run_batch()
        self.assertEqual([e["status"] for e in logs], ["FOUT"])
        self.assertIn("overgeslagen", logs[0]["msg"])
        self.assertEqual(self.backup.read_bytes(), ORIGINAL)
        self.assertEqual(self.signed.read_bytes(), b"C2PA" + ORIGINAL)

    def test_copy_fails_halfway_restores_original(self):
        with no_rename(), copy_fails_into(self.original):
            logs = self.run_batch()
        self.assertEqual([e["status"] for e in logs], ["FOUT"])
        self.assertEqual(self.original.read_bytes(), ORIGINAL)
        self.assertEqual(self.signed.read_bytes(), b"C2PA" + ORIGINAL)
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main()
