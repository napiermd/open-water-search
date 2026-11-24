"""#15: the merge rule's joins and splits, counted against labeled people with MOBDrone track IDs.

    python3 -m unittest discover -s probe

Each test runs the real command on a flight of 300 x 200 frames against a simulated Ember, as test_possible_people.py
does: every overview ranks the center tile first and the one close look opens it. The center tile spans x 100 to 200
and y 66 to 133, so a point at (u, 0.5) lands at x = 100 + 100u, y = 99.5. The merge rule's reach is 30 pixels.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from simulated_ember import SimulatedEmber, frame_name, run_command, write_flight

SCRIPT = Path(__file__).resolve().parent / "check_merge_rule.py"
WIDTH, HEIGHT = 300, 200


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def write_scoring(folder, seconds):
    """A scoring-only folder in the layout cut_mobdrone_clip.py writes. seconds lists, for each frame of the flight,
    its labeled people as (track ID or None, x1, x2), each box spanning y 90 to 110."""
    (folder / "labels").mkdir(parents=True)
    rows, tracks = [], {}
    for index, people in enumerate(seconds):
        name = frame_name(index)
        raw = "".join(f"0 {(x1 + x2) / 2 / WIDTH} {100 / HEIGHT} {(x2 - x1) / WIDTH} {20 / HEIGHT}\n"
                      for _, x1, x2 in people).encode()
        (folder / "labels" / f"{name}.txt").write_bytes(raw)
        rows.append(dict(frame=name, label=f"labels/{name}.txt", sha256=sha256(raw)))
        tracks[name] = [track for track, _, _ in people]
    raw = json.dumps(tracks).encode()
    (folder / "labels" / "tracks.json").write_bytes(raw)
    (folder / "manifest.json").write_text(json.dumps(dict(tracks="labels/tracks.json", tracks_sha256=sha256(raw),
                                                          frames=rows)))
    return folder


class MergeRuleCheck(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def search(self, center_answers):
        """Search a flight whose center close looks give these answers. Returns the search record's path."""
        flight = write_flight(self.folder / "flight", [(WIDTH, HEIGHT)] * len(center_answers))
        replies = {}
        for index, answer in enumerate(center_answers):
            replies[frame_name(index), -1] = '{"tiles":[4]}'
            replies[frame_name(index), 4] = answer
        out = self.folder / "results"
        status, printed = run_command([str(flight), "--out", str(out), "--looks", "1"], SimulatedEmber(replies))
        self.assertEqual(status, 0, printed)
        return out / "search-record.json"

    def check(self, center_answers, labeled):
        """The merge-rule report for a search with these center answers, against these labels."""
        record = self.search(center_answers)
        scoring = write_scoring(self.folder / "scoring-only", labeled)
        done = subprocess.run([sys.executable, str(SCRIPT), str(record), str(scoring)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_one_person_seen_every_second_is_one_possible_person_with_no_join_or_split(self):
        seen = '{"points":[[0.5,0.5,0.8]]}'
        report = self.check([seen, seen, seen], [[(7, 140, 160)]] * 3)
        self.assertEqual((report["possible_people"], report["labeled_people"], report["labeled_people_sighted"]), (1, 1, 1))
        self.assertEqual((report["joined_two_different_people"], report["labeled_people_split"]), (0, 0))
        self.assertEqual(report["by_possible_person"], [dict(number=1, first_seen_second=0, last_seen_second=2,
                                                             labeled_people=[7])])

    def test_a_possible_person_holding_two_people_labeled_in_the_same_second_joined_two_different_people(self):
        # Person 1 at x 105-115 and person 2 at x 125-135 are both labeled in both seconds. The sightings at x 110 and
        # then x 130 are 20 pixels apart, so the rule merges them.
        both = [(1, 105, 115), (2, 125, 135)]
        report = self.check(['{"points":[[0.1,0.5,0.8]]}', '{"points":[[0.3,0.5,0.8]]}'], [both, both])
        self.assertEqual(report["possible_people"], 1)
        self.assertEqual((report["joined_two_different_people"], report["joined_people_never_labeled_together"]), (1, 0))

    def test_people_never_labeled_in_the_same_second_may_be_one_person_and_count_as_unknown(self):
        report = self.check(['{"points":[[0.1,0.5,0.8]]}', '{"points":[[0.3,0.5,0.8]]}'],
                            [[(3, 105, 115)], [(4, 125, 135)]])
        self.assertEqual((report["joined_two_different_people"], report["joined_people_never_labeled_together"]), (0, 1))

    def test_splits_are_counted_after_gaps_of_more_than_two_seconds_and_within_two_seconds(self):
        # Person 5 is labeled for six seconds and sighted at seconds 0 and 4. At second 5 it is sighted twice, and a
        # possible person takes one sighting a second, so the second sighting starts a third possible person.
        seen = '{"points":[[0.5,0.5,0.8]]}'
        report = self.check([seen, "[]", "[]", "[]", seen, '{"points":[[0.5,0.5,0.8],[0.6,0.5,0.7]]}'],
                            [[(5, 100, 200)]] * 6)
        self.assertEqual((report["possible_people"], report["labeled_people_split"]), (3, 1))
        self.assertEqual(report["splits"], {"after_a_gap_of_more_than_2_seconds": 1, "within_2_seconds": 1})

    def test_sightings_on_a_box_without_a_track_id_or_on_no_box_are_left_out(self):
        report = self.check(['{"points":[[0.1,0.5,0.8],[0.9,0.5,0.7]]}'], [[(None, 105, 115)]])
        self.assertEqual(report["sightings"], {"on_a_labeled_person": 0, "on_a_box_without_a_track_id": 1,
                                               "on_no_labeled_person": 1})
        self.assertEqual((report["labeled_people"], report["labeled_people_sighted"]), (0, 0))

    def test_track_ids_that_differ_from_the_manifest_are_refused(self):
        record = self.search(['{"points":[[0.5,0.5,0.8]]}'])
        scoring = write_scoring(self.folder / "scoring-only", [[(7, 140, 160)]])
        (scoring / "labels" / "tracks.json").write_text(json.dumps({frame_name(0): [8]}))
        done = subprocess.run([sys.executable, str(SCRIPT), str(record), str(scoring)], capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("tracks.json does not match", done.stderr)


if __name__ == "__main__":
    unittest.main()
