"""#11: one scoring rule for Ember's search records and a trained detector's boxes.

    python3 -m unittest discover -s probe

A sighting is found when it lands inside a labeled swimmer box. Each box is found once, each photo keeps its five
most confident sightings, and only swimmers count. Expected numbers below are worked out by hand from the fixtures.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import ROOT
from score import TRAINING, VALIDATION
from score import load_sealed
from simulated_ember import SimulatedEmber, run_command, write_flight

SWIMMER, BOAT = 0, 1
# Labeled boxes in pixels of two 300 x 200 frames. Tile 4 (the center) spans x 100-200 and y 66-133.
SWIMMER_A = [140, 90, 160, 110]
SWIMMER_B = [165, 80, 175, 92]
SWIMMER_D = [250, 150, 270, 170]
BOAT_BOX = [100, 66, 130, 90]
SWIMMER_C = [10, 10, 20, 20]
SWIMMER_E = [200, 100, 210, 110]
LABELS = {"frame-01": [(SWIMMER, SWIMMER_A), (SWIMMER, SWIMMER_B), (BOAT, BOAT_BOX), (SWIMMER, SWIMMER_D)],
          "frame-02": [(SWIMMER, SWIMMER_C), (SWIMMER, SWIMMER_E)]}


def write_scoring_folder(folder, width=300, height=200):
    """Labels in the published scoring-only layout: YOLO normalized xywh files listed with their SHA-256."""
    (folder / "labels").mkdir(parents=True)
    rows = []
    for frame, boxes in LABELS.items():
        lines = [f"{c} {(x1 + x2) / 2 / width!r} {(y1 + y2) / 2 / height!r} {(x2 - x1) / width!r} {(y2 - y1) / height!r}"
                 for c, (x1, y1, x2, y2) in boxes]
        raw = "\n".join(lines).encode()
        (folder / "labels" / f"{frame}.txt").write_bytes(raw)
        rows.append(dict(frame=frame, label=f"labels/{frame}.txt", sha256=hashlib.sha256(raw).hexdigest()))
    (folder / "manifest.json").write_text(json.dumps(dict(frames=rows)))
    return folder


def scorer(*arguments):
    """Run the scorer command and return the scorecard it prints."""
    done = subprocess.run([sys.executable, str(ROOT / "probe" / "score.py"), *map(str, arguments)],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


class ScoringRule(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.scoring = write_scoring_folder(self.folder / "scoring-only")

    def test_a_search_record_is_scored_from_its_sightings(self):
        # Six sightings in frame-01's center tile, in pixels: (150, 99.5) and (152, 99.5) inside swimmer A,
        # (110, 72.7) on the boat, (190, 126.3) and (130, 119.6) on open water, and the least confident,
        # (170, 86.1), inside swimmer B. frame-02's center tile holds nobody.
        replies = {("frame-01", -1): '{"tiles":[4]}', ("frame-02", -1): '{"tiles":[4]}',
                   ("frame-01", 4): '{"points":[[0.5,0.5,0.9],[0.52,0.5,0.8],[0.1,0.1,0.7],[0.9,0.9,0.6],'
                                    '[0.3,0.8,0.5],[0.7,0.3,0.4]]}',
                   ("frame-02", 4): "[]"}
        flight = write_flight(self.folder / "flight", [(300, 200), (300, 200)])
        out = self.folder / "results"
        status, _ = run_command([str(flight), "--out", str(out), "--looks", "1"], SimulatedEmber(replies))
        self.assertEqual(status, 0)

        card = scorer("record", out / "search-record.json", self.scoring)

        # Swimmer A is found once. B's sighting is the sixth, so the five-sighting limit drops it. The boat never counts.
        self.assertEqual((card["appearances"], card["found"], card["missed"], card["unmatched"]), (5, 1, 4, 4))
        self.assertEqual(card["frames"]["frame-01"]["unmatched"], {"duplicate": 1, "wrong_class": 1, "background": 2})
        self.assertEqual(len(card["frames"]["frame-01"]["queue"]), 5)
        self.assertEqual((card["frames"]["frame-02"]["found"], card["frames"]["frame-02"]["missed"]), (0, 2))

    def test_detector_boxes_are_scored_at_their_centers_under_the_same_rule(self):
        open_water = [[0, 0, 10, 10, 0.8, SWIMMER], [20, 0, 30, 10, 0.7, SWIMMER],
                      [40, 0, 50, 10, 0.6, SWIMMER], [60, 0, 70, 10, 0.5, SWIMMER]]
        photos = [
            {"frame": "frame-01", "width": 300, "height": 200, "boxes": [
                [*SWIMMER_A, 0.9, SWIMMER],
                [*BOAT_BOX, 0.95, BOAT],    # not a swimmer box, so it is no sighting at all
                [*SWIMMER_B, 0.2, SWIMMER],  # under 0.25 confidence
                *open_water,
                [*SWIMMER_D, 0.3, SWIMMER],  # sixth most confident swimmer box, so dropped
            ]},
            {"frame": "frame-02", "width": 300, "height": 200, "boxes": [
                [*SWIMMER_C, 0.25, SWIMMER],     # exactly 0.25 is kept
                [*SWIMMER_E, 0.2499, SWIMMER],
                [0, 0, 100, 100, 0.9, SWIMMER],  # covers swimmer C, but its center (50, 50) is open water
            ]},
        ]
        boxes = self.folder / "detector.json"
        boxes.write_text(json.dumps(photos))

        card = scorer("detector", boxes, self.scoring)

        self.assertEqual((card["appearances"], card["found"], card["missed"], card["unmatched"]), (5, 2, 3, 5))
        self.assertEqual(card["frames"]["frame-01"]["queue"],
                         [[150, 100, 0.9], [5, 5, 0.8], [25, 5, 0.7], [45, 5, 0.6], [65, 5, 0.5]])
        self.assertEqual(card["frames"]["frame-01"]["unmatched"], {"background": 4})
        self.assertEqual(card["frames"]["frame-02"]["queue"], [[50, 50, 0.9], [15, 15, 0.25]])
        self.assertEqual((card["frames"]["frame-02"]["found"], card["frames"]["frame-02"]["unmatched"]),
                         (1, {"background": 1}))


class PublishedScorecards(unittest.TestCase):
    @unittest.skipUnless((TRAINING / "scoring-only" / "labels").exists() and (VALIDATION / "scoring-only" / "labels").exists(),
                         "needs the dataset labels; fetch them with probe/fetch_frames.py")
    def test_every_published_scorecard_rebuilds_exactly(self):
        printed = [subprocess.run([sys.executable, str(ROOT / "probe" / "score.py"), *run], capture_output=True,
                                  text=True, check=True).stdout for run in ([], ["validation"])]
        self.assertEqual("".join(printed).splitlines(), [
            "experiments/zoom-first/training-30/live/score.json: matches the published scorecard",
            "experiments/zoom-first/training-30/live/score-strict.json: matches the published scorecard",
            "experiments/zoom-first/validation-30/live/score.json: matches the published scorecard",
            "experiments/zoom-first/validation-30/live/score-strict.json: matches the published scorecard"])

    def sealed_copy(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        base = Path(folder.name)
        (base / "live").mkdir()
        (base / "inputs").mkdir()
        for name in ("seal.json", "redaction.json", "trace-redacted.json"):
            shutil.copy(TRAINING / "live" / name, base / "live" / name)
        shutil.copy(TRAINING / "inputs" / "manifest.json", base / "inputs" / "manifest.json")
        return base

    def test_a_trace_that_does_not_match_its_seal_is_refused(self):
        base = self.sealed_copy()
        trace, _ = load_sealed(base)
        self.assertEqual(len(trace), 570)
        changed = base / "live" / "trace-redacted.json"
        changed.write_bytes(changed.read_bytes().replace(b'"tile": 4', b'"tile": 5', 1))
        with self.assertRaises(ValueError):
            load_sealed(base)

    def test_an_unredacted_trace_that_does_not_match_its_seal_is_refused(self):
        base = self.sealed_copy()
        shutil.copy(base / "live" / "trace-redacted.json", base / "live" / "trace.json")
        with self.assertRaises(ValueError):
            load_sealed(base)


if __name__ == "__main__":
    unittest.main()
