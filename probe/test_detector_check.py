"""--mode detector-check: a trained detector flags every frame, and Ember checks each frame's flags in one request."""
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

import open_water_search
from simulated_ember import refuse_network

# Frame 0: a flag on a person and a flag on a rock. Frame 1: nothing flagged. Frame 2: one flag Ember cannot read.
DETECTOR_BOXES = [
    dict(frame="second-00000", width=600, height=300, boxes=[
        [90, 40, 110, 60, 0.4, 0], [400, 200, 420, 220, 0.7, 0], [10, 10, 40, 40, 0.9, 1]]),
    dict(frame="second-00001", width=600, height=300, boxes=[]),
    dict(frame="second-00002", width=600, height=300, boxes=[[300, 150, 320, 170, 0.5, 0]]),
]


class ScriptedEmber:
    """Answers each frame's check from a script keyed by how many crops it carries: 2 crops get a dismissal of the
    first (the rock, more confident to the detector) and a keep of the second, and 1 crop gets an unreadable answer."""

    limits = None

    def __init__(self):
        self.requests = []

    def count(self, body):
        return 400

    def generate(self, body):
        self.requests.append(body)
        crops = sum(1 for part in body["input"][0]["content"] if part["type"] == "input_image")
        if crops == 2:
            text = json.dumps({"crops": [dict(crop=1, person=False, confidence=0.9, what="dark rock"),
                                         dict(crop=2, person=True, confidence=0.95, what="person floating on back")]})
        else:
            text = "not json"
        return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
                "usage": {"input_tokens": 400, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 60}}


def write_frames(folder):
    folder.mkdir()
    for second in range(3):
        Image.new("RGB", (600, 300), (30, 60, 70)).save(folder / f"second-{second:05}.jpg")
    return folder


class DetectorCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = TemporaryDirectory()
        root = Path(cls.folder.name)
        cls.out = root / "results"
        cls.ember = ScriptedEmber()
        cls.detected = []
        printed = io.StringIO()
        with redirect_stdout(printed), refuse_network():
            open_water_search.main([str(write_frames(root / "flight")), "--out", str(cls.out), "--mode", "detector-check"],
                                   cls.ember, detect=lambda frames: cls.detected.append(frames) or DETECTOR_BOXES)
        cls.printed = printed.getvalue()
        cls.record = json.loads((cls.out / "search-record.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_one_request_per_flagged_frame_carrying_every_swimmer_flag(self):
        self.assertEqual(len(self.ember.requests), 2)
        self.assertEqual(self.ember.requests[0]["text"]["format"]["name"], "checks")
        self.assertEqual(json.loads((self.out / "detector-boxes.json").read_text()), DETECTOR_BOXES)
        self.assertEqual(len(self.detected), 1)

    def test_only_flags_ember_keeps_become_sightings_with_its_words(self):
        sightings = self.record["sightings"]
        self.assertEqual([(s["frame"], s["x"], s["y"], s["confidence"], s["what"]) for s in sightings],
                         [("second-00000", 100, 50, 0.95, "person floating on back")])
        self.assertEqual(sightings[0]["tile"], 0)

    def test_dismissed_and_unreadable_flags_stay_in_the_search_record(self):
        timeline = {frame["frame"]: frame for frame in self.record["coverage_timeline"]}
        self.assertEqual([(f["status"], f.get("what")) for f in timeline["second-00000"]["flags"]],
                         [("dismissed", "dark rock"), ("kept", "person floating on back")])
        self.assertEqual(timeline["second-00001"]["flags"], [])
        self.assertEqual([f["status"] for f in timeline["second-00002"]["flags"]], ["unreadable"])
        self.assertNotIn("tiles", timeline["second-00000"])

    def test_handoff_message_carries_embers_words_and_what_it_dismissed(self):
        message = self.record["possible_people"][0]["handoff_message"]
        self.assertIn('Ember described it as "person floating on back"', message)
        self.assertIn("The detector flagged 2 spots in that frame, and Ember kept 1 and dismissed 1.", message)
        self.assertIn(message, self.printed)

    def test_live_view_prints_each_verdict_in_embers_words(self):
        self.assertIn('second-00000: 2 detector flags: dismiss 0.90 "dark rock" · keep 0.95 "person floating on back"',
                      self.printed)
        self.assertIn("detector: 3 flags in 2 of 3 frames", self.printed)

    def test_report_lists_the_dismissed_flags_for_a_reviewer_to_reopen(self):
        report = (self.out / "report.html").read_text()
        self.assertIn("Flags Ember dismissed", report)
        self.assertIn("Ember: “dark rock”", report)
        self.assertTrue((self.out / "crops" / "second-00000-flag1.jpg").exists())

    def test_a_detector_failure_stops_the_run_before_any_ember_call(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            ember = ScriptedEmber()

            def broken(frames):
                raise SystemExit("The detector failed")

            with self.assertRaises(SystemExit), refuse_network():
                open_water_search.main([str(write_frames(root / "flight")), "--out", str(root / "results"),
                                        "--mode", "detector-check"], ember, detect=broken)
            self.assertEqual(ember.requests, [])
            self.assertFalse((root / "results").exists())


if __name__ == "__main__":
    unittest.main()
