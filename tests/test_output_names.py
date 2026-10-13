"""Uitvoermap: twee bronbestanden met dezelfde naam mogen nooit op één
uitvoerbestand eindigen.

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


def fake_sign(src, dst, manifest_path):
    Path(dst).write_bytes(b"C2PA" + Path(src).read_bytes())
    return True, ""


class PlanOutputsTest(unittest.TestCase):
    out = Path("/uit")

    def test_keeps_relative_structure(self):
        a, b = Path("/in/a/product.jpg"), Path("/in/b/product.jpg")
        plan = app.plan_outputs([a, b], Path("/in"), self.out)
        self.assertEqual(plan, {a: self.out / "a" / "product.jpg", b: self.out / "b" / "product.jpg"})

    @unittest.skipIf(sys.platform == "win32", "Windows-paden vergelijken al hoofdletterongevoelig")
    def test_case_only_difference_gets_number(self):
        a, b = Path("/in/a/Product.jpg"), Path("/in/A/product.jpg")
        plan = app.plan_outputs([a, b], Path("/in"), self.out)
        self.assertEqual(plan[a], self.out / "a" / "Product.jpg")
        self.assertEqual(plan[b], self.out / "A" / "product (2).jpg")

    def test_without_base_numbers_around_existing_names(self):
        files = [Path("/x/product.jpg"), Path("/y/product.jpg"), Path("/z/product (2).jpg")]
        plan = app.plan_outputs(files, None, self.out)
        self.assertEqual([p.name for p in plan.values()], ["product.jpg", "product (3).jpg", "product (2).jpg"])

    def test_extensionless_names(self):
        plan = app.plan_outputs([Path("/x/product"), Path("/y/product")], None, self.out)
        self.assertEqual([p.name for p in plan.values()], ["product", "product (2)"])

    def test_no_common_base(self):
        self.assertIsNone(app.common_base([Path("/a/x.jpg"), Path("b/y.jpg")]))


class ProcessBatchOutputTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="c2pa_test_"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.a = self.dir / "in" / "a" / "product.jpg"
        self.b = self.dir / "in" / "b" / "product.jpg"
        for f, data in ((self.a, b"A" * 1000), (self.b, b"B" * 2000)):
            f.parent.mkdir(parents=True)
            f.write_bytes(data)
        for target, value in (
            ("sign_with_c2patool", fake_sign),
            ("verify_with_c2patool", lambda path, dst: (True, "")),
        ):
            p = mock.patch.object(app, target, side_effect=value)
            p.start()
            self.addCleanup(p.stop)

    def run_batch(self, **cfg):
        job_id = uuid.uuid4().hex
        app.JOBS[job_id] = {"queue": queue.Queue(), "done": False}
        self.addCleanup(app.JOBS.pop, job_id, None)
        base = {"bronsoort": "volledig", "ai_tool": "Test", "burn_icon": False, "verify": True}
        base.update(cfg)
        app.process_batch(job_id, base)
        q = app.JOBS[job_id]["queue"]
        events = []
        while not q.empty():
            events.append(q.get())
        return [(e["status"], e["file"]) for e in events if e["type"] == "log"]

    def assert_two_intact_outputs(self, out):
        self.assertEqual((out / "a" / "product.jpg").read_bytes(), b"C2PA" + b"A" * 1000)
        self.assertEqual((out / "b" / "product.jpg").read_bytes(), b"C2PA" + b"B" * 2000)

    def test_recursive_folder(self):
        logs = self.run_batch(input_dir=str(self.dir / "in"), recursive=True)
        self.assertEqual(logs, [("OK", str(Path("a/product.jpg"))), ("OK", str(Path("b/product.jpg")))])
        self.assert_two_intact_outputs(self.dir / "in" / "gelabeld")

    def test_selected_files_from_two_folders(self):
        # zoals de UI: invoermap = map van het eerste bestand
        out = self.dir / "uit"
        logs = self.run_batch(
            input_dir=str(self.a.parent), files=[str(self.a), str(self.b)], output_dir=str(out)
        )
        self.assertEqual(logs, [("OK", str(Path("a/product.jpg"))), ("OK", str(Path("b/product.jpg")))])
        self.assert_two_intact_outputs(out)

    def test_same_file_selected_twice_is_processed_once(self):
        logs = self.run_batch(input_dir=str(self.a.parent), files=[str(self.a), str(self.a)])
        self.assertEqual(logs, [("OK", "product.jpg")])

    def test_output_onto_source_is_refused(self):
        logs = self.run_batch(input_dir=str(self.a.parent), files=[str(self.a)], output_dir="<invoer>")
        self.assertEqual(logs, [("FOUT", "product.jpg")])
        self.assertEqual(self.a.read_bytes(), b"A" * 1000)


if __name__ == "__main__":
    unittest.main()
