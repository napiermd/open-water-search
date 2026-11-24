"""#9: sightings merge into possible people, and each possible person gets a handoff message written by code.

    python3 -m unittest discover -s probe
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from simulated_ember import SimulatedEmber, frame_name, run_command, write_flight


class PossiblePeople(unittest.TestCase):
    """A flight of 300 x 200 frames, one per second. Each overview ranks the center tile first, and the one close
    look per frame opens it. The center tile spans x 100 to 200 and y 66 to 133, so a point at (u, v) in that close
    look lands at x = 100 + 100u in the frame. 10% of the frame width is 30 pixels."""

    def search(self, center_answers, other_replies=(), looks=1):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200)] * len(center_answers))
        replies = dict(other_replies)
        for index, center in enumerate(center_answers):
            replies.setdefault((frame_name(index), -1), '{"tiles":[4]}')
            replies[frame_name(index), 4] = center
        out = Path(folder.name) / "results"
        status, printed = run_command([str(flight), "--out", str(out), "--looks", str(looks)], SimulatedEmber(replies))
        self.assertEqual(status, 0)
        return json.loads((out / "search-record.json").read_text()), printed

    def test_sightings_in_back_to_back_seconds_close_together_are_one_possible_person(self):
        record, _ = self.search(['{"points":[[0.5,0.5,0.6]]}', '{"points":[[0.6,0.5,0.9]]}',
                                 '{"points":[[0.7,0.5,0.7]]}'])
        [person] = record["possible_people"]
        self.assertEqual((person["first_seen_second"], person["last_seen_second"]), (0, 2))
        self.assertEqual((person["first_frame"], person["last_frame"]), ("frame-01", "frame-03"))
        self.assertEqual(person["position"], {"frame": "frame-03", "x": 170, "y": 99.5, "section": "center"})
        self.assertEqual(person["confidence"], 0.9)
        self.assertEqual([s["second"] for s in person["sightings"]], [0, 1, 2])

    def test_a_gap_of_two_seconds_keeps_one_possible_person_and_a_longer_gap_starts_a_new_one(self):
        seen = '{"points":[[0.5,0.5,0.8]]}'
        record, _ = self.search([seen, "[]", seen, "[]", "[]", seen])
        self.assertEqual([(p["first_seen_second"], p["last_seen_second"]) for p in record["possible_people"]],
                         [(0, 2), (5, 5)])

    def test_sightings_more_than_a_tenth_of_the_frame_width_apart_are_different_possible_people(self):
        # x 110 then x 145 is 35 pixels, more than 30. x 120 is within 30 pixels of both, and joins the nearer.
        record, _ = self.search(['{"points":[[0.1,0.5,0.8]]}', '{"points":[[0.45,0.5,0.8]]}',
                                 '{"points":[[0.2,0.5,0.8]]}'])
        self.assertEqual([[s["second"] for s in p["sightings"]] for p in record["possible_people"]], [[0, 2], [1]])

    def test_two_people_in_one_frame_stay_two_possible_people_as_they_move(self):
        record, _ = self.search(['{"points":[[0.1,0.5,0.8],[0.3,0.5,0.6]]}',
                                 '{"points":[[0.2,0.5,0.7],[0.4,0.5,0.9]]}'])
        people = record["possible_people"]
        self.assertEqual([[round(s["x"]) for s in p["sightings"]] for p in people], [[110, 120], [130, 140]])
        self.assertEqual([p["confidence"] for p in people], [0.8, 0.9])

    def test_each_possible_person_gets_a_fixed_format_handoff_message_without_an_ember_call(self):
        seen = '{"points":[[0.5,0.5,0.9]]}'
        record, printed = self.search([seen, '{"points":[[0.6,0.5,0.7]]}', "[]", "[]", seen])
        messages = [p["handoff_message"] for p in record["possible_people"]]
        self.assertEqual(messages, [
            "Possible person 1. First seen 0:00, last seen 0:01 into the flight, in the center section of frame-02. "
            "Confidence 0.90. 8 of the 9 sections of that frame are uninspected water.",
            "Possible person 2. First seen 0:04, last seen 0:04 into the flight, in the center section of frame-05. "
            "Confidence 0.90. 8 of the 9 sections of that frame are uninspected water."])
        for message in messages:
            self.assertIn(message + "\n", printed)
        # One overview and one close look per frame, and nothing more.
        self.assertEqual(len(record["calls"]), 10)

    def test_a_section_whose_close_look_could_not_be_read_counts_as_uninspected_water(self):
        record, _ = self.search(['{"points":[[0.5,0.5,0.9]]}'],
                                {("frame-01", -1): '{"tiles":[4,0]}', ("frame-01", 0): "not an answer"}, looks=2)
        self.assertTrue(record["possible_people"][0]["handoff_message"].endswith(
            "8 of the 9 sections of that frame are uninspected water."))


if __name__ == "__main__":
    unittest.main()
