"""Test actual engine execution across a process boundary, without API calls."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from tripbuddy_backend.bridge import BridgeError, probe


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ.get("TRIPBUDDY_ENGINE_ROOT",str(Path(__file__).resolve().parents[3]/"tour-planner")))
        cls.python = Path(os.environ.get("TRIPBUDDY_ENGINE_PYTHON",str(cls.root/".venv/bin/python")))
        cls.runs = {s: probe(cls.root, cls.python, s) for s in ("course", "clarification", "abstain", "edit", "failure")}

    def test_course_uses_real_validator_and_stored_fallback(self):
        final = self.runs["course"][-1]
        self.assertEqual(final["type"], "completed")
        answer = final["answers"][0]
        self.assertEqual(answer["kind"], "course")
        self.assertEqual(len(answer["days"][0]["slots"]), 5)
        self.assertEqual(final["states"][0]["violations"], [])
        self.assertIn("저장분", answer["text"])
        self.assertTrue(all(s["id"].startswith("fixture-") for s in answer["days"][0]["slots"]))

    def test_clarification_retains_prior_conditions(self):
        final = self.runs["clarification"][-1]
        self.assertEqual([a["kind"] for a in final["answers"]], ["ask_back", "course"])
        self.assertEqual(final["answers"][0]["missing"], ["start_date"])
        self.assertEqual(final["states"][1]["request"]["region"], "강릉")
        self.assertEqual(final["states"][1]["request"]["days"], 1)

    def test_only_requested_lunch_changes(self):
        final = self.runs["edit"][-1]
        self.assertEqual(final["states"][1]["mode"], "edit")
        before, after = [a["days"][0]["slots"] for a in final["answers"]]
        self.assertEqual([a["slot"] for a, b in zip(before, after) if a["id"] != b["id"]], ["점심"])
        self.assertEqual(final["states"][1]["violations"], [])

    def test_empty_and_failed_searches_abstain_after_bounded_retry(self):
        for name in ("abstain", "failure"):
            final = self.runs[name][-1]
            self.assertEqual(final["answers"][0]["kind"], "abstain")
            self.assertEqual(final["states"][0]["retries"]["search"], 2)

    def test_offline_ui_independent_and_sequenced(self):
        for name, events in self.runs.items():
            with self.subTest(name=name):
                self.assertEqual(events[-1]["type"], "completed")
                self.assertEqual(events[-1]["network_attempts"], 0)
                self.assertFalse(events[-1]["streamlit_imported"])
                self.assertFalse(events[-1]["persistent_storage"])
                self.assertEqual([e["id"] for e in events], list(range(1, len(events) + 1)))
                self.assertTrue(any(e["type"] == "progress" for e in events))

    def test_unrelated_parent_working_directory(self):
        original = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.chdir(directory)
                self.assertEqual(probe(self.root, self.python)[-1]["type"], "completed")
        finally:
            os.chdir(original)

    def test_invalid_root(self):
        with self.assertRaisesRegex(BridgeError, "engine_source_missing"):
            probe(Path("/not-an-engine"), self.python)

    def test_timeout_is_safe(self):
        with patch("tripbuddy_backend.bridge.subprocess.run", side_effect=subprocess.TimeoutExpired("private", 1)):
            with self.assertRaisesRegex(BridgeError, "^engine_timeout$"):
                probe(self.root, self.python)

    def test_invalid_protocol_is_safe(self):
        for out in ("not JSON", '{"id":1,"type":"progress"}\n', '[1,2]\n'):
            with self.subTest(out=out), patch("tripbuddy_backend.bridge.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout=out, stderr="secret")):
                with self.assertRaisesRegex(BridgeError, "^engine_protocol_invalid$"):
                    probe(self.root, self.python)
