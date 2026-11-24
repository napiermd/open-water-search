"""#16: a MOBDrone video becomes the live run's clip, with labels for each second the search tool cuts from it.

    python3 -m unittest discover -s probe

A synthetic 9.99 frames-a-second video stands in for MOBDrone. Frame i is flat gray at level 4 i and carries one
labeled person whose box starts i pixels from the left, so both a cut frame and its label show their frame number.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageStat

from open_water_search import cut_into_seconds, load_frames
from score import groundtruth
from test_extract_mobdrone import HEIGHT, WIDTH, write_video

SCRIPT = Path(__file__).resolve().parent / "cut_mobdrone_clip.py"
RATE = "10000/1001"
LEVEL_STEP = 4
FRAMES = 60
NAME = "DJI_0804_0001_30m_1.mp4"


def track_of(frame):
    """Frames 0-19 show person 100, 21-39 person 101 and 40-59 person 102. Frame 20's box has no track ID."""
    return None if frame == 20 else 100 + frame // 20


def write_data(folder):
    (folder / "videos").mkdir(parents=True)
    video = write_video(folder / "videos" / NAME, FRAMES, rate=RATE, level_step=LEVEL_STEP)
    (folder / "frames.json").write_text(json.dumps(dict(videos=[video], frames=[])))
    images = [dict(id=frame, width=WIDTH, height=HEIGHT, file_name=f"DJI_0804_0001_30m_1_{frame:06}.PNG")
              for frame in range(FRAMES)]
    annotations = [dict(image_id=frame, category_id=1, bbox=[frame, 2, 4, 4],
                        attributes={} if track_of(frame) is None else dict(track_id=track_of(frame)))
                   for frame in range(FRAMES)]
    (folder / "annotations_person_coco_classes.json").write_text(json.dumps(dict(images=images, annotations=annotations)))
    return folder


class CutMobdroneClip(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.data = write_data(self.folder / "data")
        self.clip = self.folder / "clip"
        self.repo = self.folder / "mobdrone-clip"

    def cut(self, first_frame, seconds):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.data), NAME, str(first_frame), str(self.clip),
                               "--seconds", str(seconds), "--list", str(self.data / "frames.json"),
                               "--out", str(self.repo)], capture_output=True, text=True)

    def test_each_seconds_label_belongs_to_the_frame_the_search_tool_cuts_for_that_second(self):
        self.assertEqual(self.cut(7, 4).returncode, 0)
        frames = load_frames(cut_into_seconds(self.clip / "clip.mp4"))
        shown = [round(ImageStat.Stat(Image.open(frame["path"]).convert("L")).mean[0] / LEVEL_STEP) for frame in frames]
        # The search record's coverage timeline names each frame as cut_into_seconds() did.
        timeline = [dict(frame=frame["name"], width=frame["width"], height=frame["height"]) for frame in frames]
        labels = groundtruth(self.clip / "scoring-only", timeline)
        labeled = [round(labels[frame["frame"]][0][1][0]) for frame in timeline]
        self.assertEqual(len(frames), 4)
        self.assertEqual(labeled, shown)
        # The cut keeps the last frame before each half second: 7 + 4, 7 + 14, ...
        self.assertEqual(shown, [11, 21, 31, 41])

    def test_the_manifest_records_the_clip_and_the_track_id_of_every_labeled_person(self):
        self.cut(7, 4)
        manifest = json.loads((self.clip / "scoring-only" / "manifest.json").read_text())
        clip = self.clip / "clip.mp4"
        self.assertEqual(manifest["clip"], dict(file="clip.mp4", sha256=hashlib.sha256(clip.read_bytes()).hexdigest(),
                                                video=NAME, first_frame=7, frames=40, frame_rate=RATE, seconds=4))
        self.assertEqual([row["video_frame"] for row in manifest["frames"]], [11, 21, 31, 41])
        tracks = self.clip / "scoring-only" / manifest["tracks"]
        self.assertEqual(manifest["tracks_sha256"], hashlib.sha256(tracks.read_bytes()).hexdigest())
        self.assertEqual(json.loads(tracks.read_text()), {"second-00000": [100], "second-00001": [101],
                                                          "second-00002": [101], "second-00003": [102]})
        self.assertEqual((self.repo / "scoring-only" / "manifest.json").read_text(),
                         (self.clip / "scoring-only" / "manifest.json").read_text())
        self.assertEqual((self.repo / "scoring-only" / "labels").resolve(), (self.clip / "scoring-only" / "labels").resolve())

    def test_a_clip_running_past_the_end_of_the_video_is_refused(self):
        done = self.cut(30, 4)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("runs past the end", done.stderr)
        self.assertFalse((self.clip / "clip.mp4").exists())


if __name__ == "__main__":
    unittest.main()
