"""#15: the 300 committed MOBDrone frames become a flight folder, an inputs manifest and a scoring-only manifest.

    python3 -m unittest discover -s probe

Two synthetic videos stand in for MOBDrone. Every frame is one flat gray, 20 levels brighter than the frame
before, so an extracted photo shows which frame number it came from.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageStat

from score import groundtruth

SCRIPT = Path(__file__).resolve().parent / "extract_mobdrone.py"
WIDTH, HEIGHT = 64, 36
RATE = "30000/1001"
LEVEL_STEP = 20


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_video(path, frames, rate=RATE, level_step=LEVEL_STEP):
    """A video of flat gray frames, frame i at gray level level_step * i, at 29.97 frames a second unless rate says."""
    raw = b"".join(bytes([level_step * i]) * (WIDTH * HEIGHT) for i in range(frames))
    subprocess.run(["ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{WIDTH}x{HEIGHT}",
                    "-framerate", rate, "-i", "-", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(path)],
                   input=raw, check=True)
    return dict(video=path.name, sha256=sha256(path), frame_count=frames, frame_rate=rate)


def write_data(folder):
    """Two videos, a frame list choosing two frames from each, and a COCO person label file for every frame.

    The second video is named like the MOBDrone video whose labels use a different stem."""
    (folder / "videos").mkdir(parents=True)
    videos = [write_video(folder / "videos" / "DJI_0804_0001_30m_1.mp4", 12),
              write_video(folder / "videos" / "DJI_0915_0007_40.mp4", 10)]
    chosen = [("DJI_0804_0001_30m_1.mp4", 3), ("DJI_0804_0001_30m_1.mp4", 11),
              ("DJI_0915_0007_40.mp4", 0), ("DJI_0915_0007_40.mp4", 7)]
    listing = dict(dataset="synthetic", source="none", license="none", selection={}, videos=videos,
                   frames=[dict(video=video, frame=frame, time=0) for video, frame in chosen])
    (folder / "frames.json").write_text(json.dumps(listing))
    images = [dict(id=index, width=WIDTH, height=HEIGHT, file_name=f"{stem}_{frame:06}.PNG")
              for index, (stem, frame) in enumerate([("DJI_0804_0001_30m_1", f) for f in range(12)] +
                                                    [("DJI_0915_0007_40m", f) for f in range(10)])]
    by_name = {image["file_name"]: image["id"] for image in images}
    annotations = [dict(image_id=by_name["DJI_0804_0001_30m_1_000003.PNG"], category_id=1, bbox=[16, 9, 8, 6],
                        attributes=dict(track_id=0)),
                   dict(image_id=by_name["DJI_0804_0001_30m_1_000003.PNG"], category_id=1, bbox=[0, 0, 32, 18],
                        attributes=dict(track_id=1)),
                   dict(image_id=by_name["DJI_0915_0007_40m_000007.PNG"], category_id=1, bbox=[48, 27, 16, 9],
                        attributes={})]
    (folder / "annotations_person_coco_classes.json").write_text(json.dumps(dict(images=images, annotations=annotations)))
    return folder


class ExtractMobdrone(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.data = write_data(self.folder / "data")
        self.sample = self.folder / "sample"
        self.repo = self.folder / "mobdrone"

    def extract(self):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.data), str(self.sample),
                               "--list", str(self.data / "frames.json"), "--out", str(self.repo)],
                              capture_output=True, text=True)

    def test_photos_are_the_chosen_frame_numbers_in_the_committed_order(self):
        self.assertEqual(self.extract().returncode, 0)
        names = sorted(path.stem for path in (self.sample / "images").iterdir())
        self.assertEqual(names, ["001-DJI_0804_0001_30m_1-000003", "002-DJI_0804_0001_30m_1-000011",
                                 "003-DJI_0915_0007_40-000000", "004-DJI_0915_0007_40-000007"])
        levels = [ImageStat.Stat(Image.open(self.sample / "images" / f"{name}.jpg").convert("L")).mean[0]
                  for name in names]
        for level, frame in zip(levels, [3, 11, 0, 7]):
            self.assertAlmostEqual(level, LEVEL_STEP * frame, delta=3)

    def test_the_inputs_manifest_lists_each_photo_with_its_size_and_sha256(self):
        self.extract()
        manifest = json.loads((self.repo / "inputs" / "manifest.json").read_text())
        first = manifest["frames"][0]
        self.assertEqual({key: first[key] for key in ("frame", "image", "video", "video_frame", "width", "height")},
                         dict(frame="001-DJI_0804_0001_30m_1-000003", image="images/001-DJI_0804_0001_30m_1-000003.jpg",
                              video="DJI_0804_0001_30m_1.mp4", video_frame=3, width=WIDTH, height=HEIGHT))
        for row in manifest["frames"]:
            self.assertEqual(row["sha256"], sha256(self.repo / "inputs" / row["image"]))
        self.assertEqual(manifest["list_sha256"], sha256(self.data / "frames.json"))

    def test_person_boxes_become_class_0_labels_the_scorer_reads_in_pixels(self):
        self.extract()
        frames = json.loads((self.repo / "inputs" / "manifest.json").read_text())["frames"]
        # Label files keep six decimals, so boxes come back to within a hundredth of a pixel.
        labels = {frame: [(cls, [round(n, 2) for n in box]) for cls, box in boxes]
                  for frame, boxes in groundtruth(self.repo / "scoring-only", frames).items()}
        self.assertEqual(labels["001-DJI_0804_0001_30m_1-000003"], [(0, [16, 9, 24, 15]), (0, [0, 0, 32, 18])])
        self.assertEqual(labels["002-DJI_0804_0001_30m_1-000011"], [])
        # The video named DJI_0915_0007_40.mp4 has its labels under DJI_0915_0007_40m.
        self.assertEqual(labels["004-DJI_0915_0007_40-000007"], [(0, [48, 27, 64, 36])])

    def test_a_video_that_does_not_match_the_frame_list_is_refused(self):
        listing = json.loads((self.data / "frames.json").read_text())
        listing["videos"][1]["sha256"] = "0" * 64
        (self.data / "frames.json").write_text(json.dumps(listing))
        done = self.extract()
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("DJI_0915_0007_40.mp4 does not match", done.stderr)
        self.assertFalse((self.repo / "inputs" / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
