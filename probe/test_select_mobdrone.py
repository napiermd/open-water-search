"""Run select_mobdrone.py on 66 short synthetic videos and check the frame list it writes.

    python probe/test_select_mobdrone.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "select_mobdrone.py"
FPS = 10


def make_videos(folder):
    """66 videos of 2 to 7 seconds at 10 frames a second, so frame counts differ between videos."""
    counts = {}
    for number in range(66):
        seconds = 2 + number % 6
        name = f"clip_{number:02}.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=64x48:rate={FPS}:duration={seconds}",
             "-pix_fmt", "yuv420p", str(folder / name)],
            check=True,
        )
        counts[name] = seconds * FPS
    return counts


class SelectMobdrone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        cls.videos = cls.folder / "videos"
        cls.videos.mkdir()
        cls.counts = make_videos(cls.videos)
        cls.first = cls.folder / "first.json"
        subprocess.run([sys.executable, str(SCRIPT), str(cls.videos), str(cls.first)], check=True, capture_output=True)
        cls.listing = json.loads(cls.first.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def frames_by_video(self):
        grouped = {}
        for frame in self.listing["frames"]:
            grouped.setdefault(frame["video"], []).append(frame)
        return grouped

    def test_300_frames_spread_over_all_66_videos(self):
        grouped = self.frames_by_video()
        self.assertEqual(len(self.listing["frames"]), 300)
        self.assertEqual(set(grouped), set(self.counts))
        sizes = sorted(len(frames) for frames in grouped.values())
        self.assertEqual(sizes, [4] * 30 + [5] * 36)

    def test_each_video_contributes_one_frame_from_each_equal_stretch(self):
        for video, frames in self.frames_by_video().items():
            count, picks = self.counts[video], len(frames)
            for stretch, frame in enumerate(frames):
                self.assertGreaterEqual(frame["frame"], stretch * count // picks, video)
                self.assertLess(frame["frame"], (stretch + 1) * count // picks, video)

    def test_timestamps_follow_the_frame_rate(self):
        for frame in self.listing["frames"]:
            self.assertAlmostEqual(frame["time"], frame["frame"] / FPS, places=3)

    def test_records_frame_count_and_sha256_of_every_video(self):
        recorded = {video["video"]: video for video in self.listing["videos"]}
        self.assertEqual(set(recorded), set(self.counts))
        for name, count in self.counts.items():
            self.assertEqual(recorded[name]["frame_count"], count)
            self.assertEqual(recorded[name]["sha256"], hashlib.sha256((self.videos / name).read_bytes()).hexdigest())

    def test_same_videos_give_the_same_list(self):
        second = self.folder / "second.json"
        subprocess.run([sys.executable, str(SCRIPT), str(self.videos), str(second)], check=True, capture_output=True)
        self.assertEqual(second.read_bytes(), self.first.read_bytes())

    def test_refuses_to_replace_an_existing_list(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.videos), str(self.first)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
