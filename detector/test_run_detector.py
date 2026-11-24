"""#13: the trained detector's boxes, in the shape probe/score.py detector mode reads.

    python3 -m unittest discover -s detector

A stand-in replaces the YOLO model, so these checks need neither ultralytics nor the weights.
"""
import ast
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from run_detector import ROOT, run

STAND_IN = {"name": "corner-box stand-in"}


def corner_box(crops):
    """Stand-in model: one swimmer box at the top-left corner of every image it is given."""
    return [[[0.0, 0.0, 10.0, 10.0, 0.5, 0.0]] for _ in crops]


def write_inputs(folder, width=301, height=200):
    """One photo in the repo's inputs layout: images/ and a manifest listing each image with its size and SHA-256."""
    (folder / "images").mkdir(parents=True)
    Image.new("RGB", (width, height), (20, 60, 90)).save(folder / "images" / "frame-01.jpg")
    raw = (folder / "images" / "frame-01.jpg").read_bytes()
    frames = [dict(frame="frame-01", image="images/frame-01.jpg", width=width, height=height,
                   sha256=hashlib.sha256(raw).hexdigest())]
    (folder / "manifest.json").write_text(json.dumps(dict(frames=frames)))
    return folder / "manifest.json"


def write_scoring_folder(folder, swimmer, width=301, height=200):
    """frame-01's one labeled swimmer box in the scoring-only layout: a YOLO normalized xywh file and its SHA-256."""
    (folder / "labels").mkdir(parents=True)
    x1, y1, x2, y2 = swimmer
    raw = f"0 {(x1 + x2) / 2 / width} {(y1 + y2) / 2 / height} {(x2 - x1) / width} {(y2 - y1) / height}".encode()
    (folder / "labels" / "frame-01.txt").write_bytes(raw)
    rows = [dict(frame="frame-01", label="labels/frame-01.txt", sha256=hashlib.sha256(raw).hexdigest())]
    (folder / "manifest.json").write_text(json.dumps(dict(frames=rows)))
    return folder


class DetectorRun(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.inputs = write_inputs(self.folder / "inputs")
        self.out = self.folder / "run"

    def test_tile_boxes_come_back_in_photo_pixels(self):
        # A 301 x 200 photo splits into tiles starting at x 0, 100, 200 and y 0, 66, 133, as in runner.rectangle().
        run(self.inputs, self.out, tiles=True, predict=corner_box, model=STAND_IN)

        photos = json.loads((self.out / "boxes.json").read_text())
        self.assertEqual(photos, [{"frame": "frame-01", "width": 301, "height": 200, "boxes": [
            [0, 0, 10, 10, 0.5, 0], [100, 0, 110, 10, 0.5, 0], [200, 0, 210, 10, 0.5, 0],
            [0, 66, 10, 76, 0.5, 0], [100, 66, 110, 76, 0.5, 0], [200, 66, 210, 76, 0.5, 0],
            [0, 133, 10, 143, 0.5, 0], [100, 133, 110, 143, 0.5, 0], [200, 133, 210, 143, 0.5, 0]]}])

    def test_a_full_frame_run_gives_the_model_the_whole_photo(self):
        seen = []

        def whole_photo(crops):
            seen.extend(crop.size for crop in crops)
            return corner_box(crops)

        run(self.inputs, self.out, tiles=False, predict=whole_photo, model=STAND_IN)

        self.assertEqual(seen, [(301, 200)])
        self.assertEqual(json.loads((self.out / "boxes.json").read_text())[0]["boxes"], [[0, 0, 10, 10, 0.5, 0]])

    def test_the_scorer_reads_the_boxes_in_detector_mode(self):
        # A swimmer labeled at the corner of the center tile. Equal confidences keep tiles 0-4 in the top five,
        # so the center tile's box is found and the other four are open water.
        scoring = write_scoring_folder(self.folder / "scoring-only", [98, 64, 112, 78])
        run(self.inputs, self.out, tiles=True, predict=corner_box, model=STAND_IN)

        done = subprocess.run([sys.executable, str(ROOT / "probe" / "score.py"), "detector",
                               str(self.out / "boxes.json"), str(scoring)], capture_output=True, text=True, check=True)
        card = json.loads(done.stdout)

        self.assertEqual((card["appearances"], card["found"], card["missed"], card["unmatched"]), (1, 1, 0, 4))
        self.assertEqual(card["frames"]["frame-01"]["unmatched"], {"background": 4})

    def test_the_seal_holds_the_sha256_of_the_boxes_and_of_the_inputs_list(self):
        run(self.inputs, self.out, tiles=True, predict=corner_box, model=STAND_IN)

        seal = json.loads((self.out / "seal.json").read_text())
        self.assertEqual(seal["boxes_sha256"], hashlib.sha256((self.out / "boxes.json").read_bytes()).hexdigest())
        self.assertEqual(seal["inputs_sha256"], hashlib.sha256(self.inputs.read_bytes()).hexdigest())
        self.assertEqual((seal["photos"], seal["tiles"], seal["model"]), (1, "3 x 3, as probe/runner.py rectangle()", STAND_IN))

    def test_a_photo_that_does_not_match_the_inputs_list_is_refused(self):
        Image.new("RGB", (301, 200), (0, 0, 0)).save(self.inputs.parent / "images" / "frame-01.jpg")

        with self.assertRaises(ValueError):
            run(self.inputs, self.out, tiles=True, predict=corner_box, model=STAND_IN)
        self.assertFalse((self.out / "boxes.json").exists())


class Separation(unittest.TestCase):
    def test_the_search_tool_imports_nothing_from_the_detector_folder(self):
        detector_modules = {path.stem for path in (ROOT / "detector").glob("*.py")} | {"detector", "ultralytics"}
        for path in (ROOT / "probe").glob("*.py"):
            imported = set()
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    imported |= {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(imported & detector_modules, path.name)


if __name__ == "__main__":
    unittest.main()
