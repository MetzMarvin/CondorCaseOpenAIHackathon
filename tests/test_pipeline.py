"""Integration checks against the pinned real upstream snapshot."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.cli import ROOT, allocate, build, clean, expectation, load_source, read_json, read_rows, validate


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "complaints"

    def generate(self, out=None, count=30):
        with contextlib.redirect_stdout(io.StringIO()):
            build(ROOT / "config/complaints.json", ROOT / "config/wording.json", out or self.out, count, 261)

    def test_source_integrity_and_actual_relationships(self):
        manifest, db, tasks = load_source()
        self.assertEqual(len(manifest["revision"]), 40)
        self.assertEqual((len(db["flights"]), len(db["users"]), len(db["reservations"]), len(tasks)), (300, 500, 2000, 50))

    def test_rebuild_is_byte_identical(self):
        self.generate()
        other = Path(self.temp.name) / "second"
        self.generate(other)
        files = {str(p.relative_to(self.out)): p.read_bytes() for p in self.out.rglob("*") if p.is_file()}
        other_files = {str(p.relative_to(other)): p.read_bytes() for p in other.rglob("*") if p.is_file()}
        self.assertEqual(files, other_files)
        self.generate()
        self.assertEqual(files, {str(p.relative_to(self.out)): p.read_bytes() for p in self.out.rglob("*") if p.is_file()})

    def test_mock_paths_and_private_replies(self):
        self.generate(count=100)
        labels = read_rows(self.out / "evaluation/labels.jsonl")
        actions = {r["expected_next_action"] for r in labels}
        self.assertTrue({"resolve_demo", "request_missing_info", "request_clarification", "escalate_human"} <= actions)
        cases = read_rows(self.out / "runtime/cases.jsonl")
        self.assertEqual(sum(r["language"] == "de" for r in cases), 80)
        runtime = "\n".join(p.read_text() for p in (self.out / "runtime").glob("*.jsonl"))
        self.assertNotIn('"expected_next_action"', runtime)
        self.assertNotIn('"source_task_family_id"', runtime)
        simulator = read_rows(self.out / "evaluation/simulator.jsonl")
        self.assertTrue(simulator)
        for reply in simulator:
            self.assertIn(reply["expected_after_reply"], ("resolve_demo", "escalate_human"))
            self.assertNotIn(reply["reply_body"], runtime)
            for upload in reply["attachments"]:
                self.assertTrue((self.out / "evaluation" / upload["path"]).is_file())
                self.assertFalse((self.out / "runtime" / upload["path"]).exists())

    def test_validation_rejects_corrupt_case_link(self):
        self.generate()
        path = self.out / "runtime/cases.jsonl"
        rows = read_rows(path)
        rows[0]["booking_id"] = "UNKNOWN"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        with self.assertRaisesRegex(ValueError, "Unknown booking"):
            validate(self.out)

    def test_validation_rejects_changed_evidence(self):
        self.generate()
        attachment = next((self.out / "runtime/attachments").glob("*.pdf"))
        attachment.write_bytes(b"wrong evidence")
        with self.assertRaisesRegex(ValueError, "Evidence content mismatch"):
            validate(self.out)

    def test_does_not_overwrite_user_directory(self):
        self.out.mkdir()
        existing = self.out / "important.txt"
        existing.write_text("keep")
        with self.assertRaisesRegex(ValueError, "Refusing"):
            self.generate()
        self.assertEqual(existing.read_text(), "keep")

    def test_angry_tone_does_not_trigger_escalation(self):
        policy = read_json(ROOT / "config/complaints.json")["policy"]
        self.assertEqual(expectation("service", "complete", policy), expectation("service", "angry_complete", policy))
        self.assertEqual(expectation("service", "serious", policy)[0], "escalate_human")
        self.assertEqual(expectation("denied_boarding", "complete", policy)[0], "escalate_human")

    def test_cleaning_and_allocation(self):
        self.assertEqual(clean("  Hallo\x00\r\n\r\n  A\t B  "), "Hallo\n\nA B")
        self.assertEqual(len(allocate({"a": 70, "b": 15, "c": 15}, 31)), 31)
        with self.assertRaises(ValueError):
            allocate({"a": 1}, 0)

    def test_baggage_uploads_and_specific_questions(self):
        config = read_json(ROOT / "config/complaints.json")
        config["category_weights"] = {"baggage": 1}
        path = Path(self.temp.name) / "baggage.json"
        path.write_text(json.dumps(config))
        with contextlib.redirect_stdout(io.StringIO()):
            build(path, ROOT / "config/wording.json", self.out, 13, 261)
        labels = read_rows(self.out / "evaluation/labels.jsonl")
        cases = {r["id"]: r for r in read_rows(self.out / "runtime/cases.jsonl")}
        attachments = read_rows(self.out / "runtime/attachments.jsonl")
        references = read_rows(self.out / "evaluation/evidence_labels.jsonl")
        refs = {r["attachment_id"]:r for r in references}
        replies = {r["case_id"]:r for r in read_rows(self.out / "evaluation/simulator.jsonl")}
        self.assertTrue({"application/pdf", "image/png"} <= {a["media_type"] for a in attachments})
        for scenario, field in [("missing_pir", "pir_reference"), ("missing_bag_tag", "bag_tag")]:
            label = next(r for r in labels if r["scenario"] == scenario)
            initial = [a for a in attachments if a["case_id"] == label["case_id"]]
            self.assertFalse(any(field in refs[a["id"]]["expected_fields"] for a in initial))
            reply = replies[label["case_id"]]
            self.assertTrue(any(field in refs[a["id"]]["expected_fields"] for a in reply["attachments"]))
            self.assertEqual(reply["question_message"]["thread_id"], reply["customer_message"]["thread_id"])
            self.assertEqual(reply["question_message"]["case_id"], label["case_id"])
        label = next(r for r in labels if r["scenario"] == "attachment_only")
        self.assertNotIn("EUR", cases[label["case_id"]]["description"])
        self.assertTrue(any("amount_eur" in refs[a["id"]]["expected_fields"] for a in attachments if a["case_id"] == label["case_id"]))
        label = next(r for r in labels if r["scenario"] == "unreadable_document")
        unreadable = [a for a in attachments if a["case_id"] == label["case_id"] and not refs[a["id"]]["readable"]]
        self.assertTrue(unreadable)
        self.assertEqual(label["expected_next_action"], "request_missing_info")


if __name__ == "__main__":
    unittest.main()
