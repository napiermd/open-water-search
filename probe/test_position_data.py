"""#10: drone position data reaches the search record only for frames that have it.

    python3 -m unittest discover -s probe
"""
import json
import re
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import write_positions
from simulated_ember import SimulatedEmber, frame_name, run_command, write_flight

SEEN = '{"points":[[0.5,0.5,0.9]]}'


class PositionData(unittest.TestCase):
    """A flight of 300 x 200 frames, one per second. Each overview ranks the center tile first, and the one close
    look per frame opens it. Sightings more than two seconds apart are different possible people."""

    def search(self, center_answers, positions=None):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200)] * len(center_answers))
        replies = {}
        for index, center in enumerate(center_answers):
            replies[frame_name(index), -1] = '{"tiles":[4]}'
            replies[frame_name(index), 4] = center
        out = Path(folder.name) / "results"
        arguments = [str(flight), "--out", str(out), "--looks", "1"]
        if positions is not None:
            sidecar = Path(folder.name) / "positions.json"
            sidecar.write_text(json.dumps(positions))
            arguments += ["--positions", str(sidecar)]
        status, printed = run_command(arguments, SimulatedEmber(replies))
        self.assertEqual(status, 0)
        return json.loads((out / "search-record.json").read_text()), printed, out

    def test_a_possible_person_seen_in_a_frame_with_position_data_gets_the_drone_position_at_sighting(self):
        positions = {"frames": {"frame-01": {"latitude": 47.672416, "longitude": 9.269057},
                                "frame-02": None}}
        record, printed, _ = self.search([SEEN, "[]", "[]", "[]", "[]"], positions)
        [person] = record["possible_people"]
        self.assertEqual(person["position"]["drone_position_at_sighting"],
                         {"latitude": 47.672416, "longitude": 9.269057})
        self.assertEqual(person["handoff_message"],
                         "Possible person 1. First seen 0:00, last seen 0:00 into the flight, "
                         "in the center section of frame-01. Drone position at sighting latitude 47.67242, "
                         "longitude 9.26906. The person's own position could not be worked out from the flight data. "
                         "Confidence 0.90. 8 of the 9 sections of that frame were never searched.")
        self.assertIn(person["handoff_message"] + "\n", printed)

    def test_a_frame_without_position_data_gets_no_coordinates_and_the_message_says_so(self):
        positions = {"frames": {"frame-01": {"latitude": 47.672416, "longitude": 9.269057},
                                "frame-02": None}}
        record, _, _ = self.search(["[]", SEEN, "[]", "[]", SEEN], positions)
        first, second = record["possible_people"]
        self.assertEqual(first["position"], {"frame": "frame-02", "x": 150, "y": 99.5, "section": "center"})
        self.assertEqual(first["handoff_message"],
                         "Possible person 1. First seen 0:01, last seen 0:01 into the flight, "
                         "in the center section of frame-02. No position data for that frame. "
                         "Confidence 0.90. 8 of the 9 sections of that frame were never searched.")
        self.assertNotIn("drone_position_at_sighting", second["position"])
        self.assertIn("No position data for that frame.", second["handoff_message"])
        self.assertEqual([frame.get("drone_position") for frame in record["coverage_timeline"]],
                         [{"latitude": 47.672416, "longitude": 9.269057}, None, None, None, None])
        self.assertEqual(record["flight"]["position_data"], "drone position for 1 of 5 frames")

    def test_a_flight_without_position_data_has_no_coordinates_anywhere_and_the_record_says_so(self):
        record, printed, out = self.search([SEEN, "[]"])
        self.assertEqual(record["flight"]["position_data"], "unavailable")
        self.assertEqual(record["possible_people"][0]["handoff_message"],
                         "Possible person 1. First seen 0:00, last seen 0:00 into the flight, "
                         "in the center section of frame-01. "
                         "Confidence 0.90. 8 of the 9 sections of that frame were never searched.")
        for written in [printed] + [path.read_text() for path in out.iterdir() if path.is_file()]:
            self.assertNotIn("latitude", written)
            self.assertNotIn("drone_position", written)
        report = (out / "report.html").read_text()
        self.assertIn("No position data came with this flight, so this report shows no coordinates or map.", report)
        self.assertNotIn("<svg", report)

    def test_the_report_maps_the_drone_position_of_only_the_frames_that_have_one(self):
        # frame-03 is about 61 metres north and 9 metres east of frame-01.
        positions = {"frames": {"frame-01": {"latitude": 47.672416, "longitude": 9.269057},
                                "frame-02": None,
                                "frame-03": {"latitude": 47.672964, "longitude": 9.269172}}}
        _, _, out = self.search([SEEN, "[]", "[]"], positions)
        report = (out / "report.html").read_text()
        dots = {frame: (float(x), float(y)) for x, y, frame in
                re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)"[^>]*><title>(frame-\d+)', report)}
        self.assertEqual(sorted(dots), ["frame-01", "frame-03"])
        self.assertGreater(dots["frame-03"][0], dots["frame-01"][0])
        self.assertLess(dots["frame-03"][1], dots["frame-01"][1])
        self.assertIn("1 of 3 frames have no position data and are not on the map.", report)
        self.assertIn("The positions span 9 m east to west and 61 m north to south.", report)
        self.assertIn("Drone position latitude 47.67242, longitude 9.26906.", report)
        self.assertIn("No position data for this frame.", report)

    def test_a_position_without_a_valid_latitude_and_longitude_stops_the_run_before_any_request(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        flight = write_flight(folder / "flight", [(300, 200)])
        sidecar = folder / "positions.json"
        sidecar.write_text(json.dumps({"frames": {"frame-01": {"latitude": 47.672416}}}))
        ember = SimulatedEmber({("frame-01", -1): '{"tiles":[4]}'})
        status, _ = run_command([str(flight), "--out", str(folder / "results"), "--positions", str(sidecar)], ember)
        self.assertEqual(status, f"{sidecar}: frame-01 needs a latitude from -90 to 90 and a longitude from -180 to 180.")
        self.assertEqual(ember.requests, [])

    def test_a_position_file_written_from_seadronessee_annotations_reaches_the_handoff_message(self):
        # The three meta layouts in the official annotations: video telemetry, a still photo whose numbers sit in
        # the _ref fields, and none at all.
        video = {"latitude": 47.672416, "longitude": 9.269057, "height_above_takeoff(meter)": 47.8,
                 "gimbal_pitch(degrees)": 36.1}
        still = {"gps_latitude_ref": 53.7217467944444, "gps_longitude_ref": 7.16250296388889, "altitude": 58.68,
                 "gimbal_pitch": 90.0}
        folder = Path(self.enterContext(TemporaryDirectory()))
        annotations = folder / "instances_val.json"
        annotations.write_text(json.dumps({"images": [{"id": 10833, "file_name": "10833.jpg", "meta": video},
                                                      {"id": 646, "file_name": "646.jpg", "meta": still},
                                                      {"id": 15355, "file_name": "15355.jpg", "meta": None}]}))
        manifest = folder / "manifest.json"
        manifest.write_text(json.dumps({"frames": [{"frame": "frame-01", "source": "shard_000/15355.jpg"},
                                                   {"frame": "frame-02", "source": "shard_000/646.jpg"},
                                                   {"frame": "frame-03", "source": "shard_000/10833.jpg"}]}))
        positions = folder / "positions.json"
        with redirect_stdout(StringIO()) as printed:
            write_positions.main([str(annotations), str(manifest), str(positions)])
        self.assertEqual(printed.getvalue(), f"2 of 3 frames have a drone position. Wrote {positions}\n")
        self.assertEqual(json.loads(positions.read_text())["frames"], {
            "frame-01": None,
            "frame-02": {"latitude": 53.7217467944444, "longitude": 7.16250296388889, "meta": still},
            "frame-03": {"latitude": 47.672416, "longitude": 9.269057, "meta": video}})
        record, _, _ = self.search(["[]", "[]", SEEN], json.loads(positions.read_text()))
        self.assertIn("Drone position at sighting latitude 47.67242, longitude 9.26906.",
                      record["possible_people"][0]["handoff_message"])


if __name__ == "__main__":
    unittest.main()
