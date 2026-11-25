"""Detector-then-Ember: Ember checks each candidate crop, and only the ones it accepts become sightings."""
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

import verify_candidates
from runner import LIMIT, NANO, price


class FakeEmber:
    """Accepts the crops listed in accept, at the given confidence; every reply costs the same."""

    def __init__(self, accept):
        self.accept = accept
        self.requests = []

    def count(self, body):
        return 300

    def generate(self, body):
        self.requests.append(body)
        crops = sum(1 for part in body["input"][0]["content"] if part["type"] == "input_image")
        verdicts = [dict(crop=n, person=n in self.accept, confidence=self.accept.get(n, 0.1), what="x")
                    for n in range(1, crops + 1)]
        return {"output": [{"content": [{"type": "output_text", "text": json.dumps({"crops": verdicts})}]}],
                "usage": {"input_tokens": 300, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 50}}


class VerifyCandidates(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "inputs/images").mkdir(parents=True)
        (self.root / "scoring/labels").mkdir(parents=True)
        frames, labels, photos = [], [], []
        for name in ("a", "b"):
            Image.new("RGB", (400, 200), (30, 60, 70)).save(self.root / f"inputs/images/{name}.jpg")
            frames.append(dict(frame=name, image=f"images/{name}.jpg", width=400, height=200))
            # One labeled swimmer centred at (100, 50): normalized 0.25, 0.25, size 0.05 x 0.1.
            text = "0 0.25 0.25 0.05 0.1\n"
            (self.root / f"scoring/labels/{name}.txt").write_text(text)
            labels.append(dict(frame=name, label=f"labels/{name}.txt", sha256=hashlib.sha256(text.encode()).hexdigest()))
            # Candidate 1 sits on the swimmer, candidate 2 on open water, and a boat box is never a candidate.
            photos.append(dict(frame=name, width=400, height=200, boxes=[
                [95, 45, 105, 55, 0.3, 0], [300, 150, 310, 160, 0.6, 0], [10, 10, 30, 30, 0.9, 1]]))
        (self.root / "inputs/manifest.json").write_text(json.dumps(dict(frames=frames)))
        (self.root / "scoring/manifest.json").write_text(json.dumps(dict(frames=labels)))
        (self.root / "candidates.json").write_text(json.dumps(photos))

    def run_check(self, ember, budget="0.05"):
        out = self.root / "out"
        verify_candidates.main([str(self.root / "candidates.json"), str(self.root / "inputs/manifest.json"),
                                str(self.root / "scoring"), "--out", str(out), "--budget", budget], ember)
        return json.loads((out / "scorecard.json").read_text()), json.loads((out / "summary.json").read_text())

    def test_only_candidates_ember_accepts_become_sightings(self):
        # Candidates go in detector-confidence order, so the open-water box is crop 1 and the swimmer crop 2.
        ember = FakeEmber({2: 0.9})
        card, summary = self.run_check(ember)
        self.assertEqual((card["found"], card["unmatched"]), (2, 0))
        self.assertEqual(summary["candidates"], 4)
        self.assertEqual(len(ember.requests), 2)
        self.assertEqual(ember.requests[0]["text"]["format"]["type"], "json_schema")

    def test_a_prompt_file_replaces_the_check_prompt_and_is_recorded(self):
        (self.root / "prompt.txt").write_text("Check each crop for a person in the water.\n")
        ember = FakeEmber({2: 0.9})
        out = self.root / "out"
        verify_candidates.main([str(self.root / "candidates.json"), str(self.root / "inputs/manifest.json"),
                                str(self.root / "scoring"), "--out", str(out), "--budget", "0.05",
                                "--prompt-file", str(self.root / "prompt.txt")], ember)
        self.assertEqual(ember.requests[0]["input"][0]["content"][0]["text"], "Check each crop for a person in the water.")
        self.assertEqual(json.loads((out / "summary.json").read_text())["settings"]["prompt"],
                         "Check each crop for a person in the water.")

    def test_without_a_prompt_file_every_request_uses_the_sealed_prompt(self):
        ember = FakeEmber({2: 0.9})
        self.run_check(ember)
        self.assertTrue(all(body["input"][0]["content"][0]["text"] == verify_candidates.PROMPT for body in ember.requests))

    def test_the_run_stops_before_a_request_could_cross_the_budget(self):
        worst = price(300 + len(json.dumps({"format": verify_candidates.CHECKS})), 0, LIMIT)
        budget = f"{(worst + 1) / NANO:.9f}"
        card, summary = self.run_check(FakeEmber({2: 0.9}), budget)
        self.assertEqual(summary["photos_checked"], 1)
        self.assertEqual(summary["ending"], "spending cap")
        self.assertLessEqual(summary["spent_nanodollars"], worst + 1)


if __name__ == "__main__":
    unittest.main()
