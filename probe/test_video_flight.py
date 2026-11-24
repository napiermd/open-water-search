"""#8: a video flight is cut into one frame per second on the operator's machine and searched like photos.

    python3 -m unittest discover -s probe
"""
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from simulated_ember import SimulatedEmber, run_command, write_flight


def write_video(flight, video):
    """Encode a fixture flight's frames as a video that shows each frame for one second."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-framerate", "1", "-start_number", "1",
                    "-i", str(flight / "frame-%02d.jpg"), "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
                    "-r", "30", str(video)], check=True)
    return video


def without_source_or_timing(record):
    """The search record minus what differs between any two runs: the input's path, the clock times of the run, of
    each call and of each decision, and the order in which parallel answers arrived."""
    record = dict(record, flight=None, seconds=None, photos_per_minute=None)
    record["calls"] = [dict(call, seconds=None, answer=dict(call["answer"], started=None, finished=None))
                       for call in record["calls"]]
    record["decision_log"] = sorted(json.dumps(dict(decision, seconds=None)) for decision in record["decision_log"])
    return record


class VideoFlight(unittest.TestCase):
    """A three-second video of three 300 x 200 fixture frames, one close look per second."""

    replies = {("frame-01", -1): '{"tiles":[4]}', ("frame-01", 4): '{"points":[[0.5,0.5,0.9]]}',
               ("frame-02", -1): '{"tiles":[0]}', ("frame-02", 0): "[]",
               ("frame-03", -1): '{"tiles":[8]}', ("frame-03", 8): '{"points":[[0.2,0.4,0.6]]}'}

    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.video = write_video(write_flight(self.folder / "flight", [(300, 200)] * 3), self.folder / "flight.mp4")

    def search(self, flight, name):
        out = self.folder / name
        status, printed = run_command([str(flight), "--out", str(out), "--looks", "1"], SimulatedEmber(self.replies))
        self.assertEqual(status, 0, printed)
        return json.loads((out / "search-record.json").read_text())

    def test_the_coverage_timeline_keys_each_frame_by_its_second_in_the_flight(self):
        timeline = self.search(self.video, "results")["coverage_timeline"]
        self.assertEqual([(frame["second"], frame["frame"]) for frame in timeline],
                         [(0, "second-00000"), (1, "second-00001"), (2, "second-00002")])
        # Each second shows the fixture frame the video showed then: its overview chose tile 4, 0 and 8.
        statuses = [{tile["tile"]: tile["status"] for tile in frame["tiles"] if tile["status"] != "not checked"}
                    for frame in timeline]
        self.assertEqual(statuses, [{4: "flagged"}, {0: "checked, no sighting"}, {8: "flagged"}])

    def test_a_video_and_the_same_frames_as_a_folder_give_the_same_search_record(self):
        from_video = self.search(self.video, "video-results")
        photos = self.folder / "flight"
        for second, path in enumerate(sorted(photos.iterdir())):
            path.rename(photos / f"second-{second:05}.jpg")
        from_photos = self.search(photos, "photo-results")
        self.assertEqual(len(from_video["sightings"]), 2)
        self.assertEqual(without_source_or_timing(from_video), without_source_or_timing(from_photos))

    def test_a_file_ffmpeg_cannot_read_stops_before_any_results_or_requests(self):
        notes = self.folder / "notes.txt"
        notes.write_text("not a video")
        status, printed = run_command([str(notes), "--out", str(self.folder / "results")], SimulatedEmber({}))
        self.assertIn(f"ffmpeg could not cut {notes} into frames", str(status))
        self.assertFalse((self.folder / "results").exists())


if __name__ == "__main__":
    unittest.main()
