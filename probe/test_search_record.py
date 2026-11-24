"""#2: a flight of photos produces one search record, and the report page, reviewer queue and coverage map are views of it.

    python3 -m unittest discover -s probe
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import ROOT
from simulated_ember import SimulatedEmber, run_command, write_flight

TOOL_TEST = ROOT / "examples" / "tool-test"
TOOL_TEST_SIZES = [(3840, 2160), (1920, 1080), (3840, 2160), (1920, 1080)]


def recorded_replies():
    """Ember's replies from the paid four-frame tool test in examples/tool-test, keyed by frame and tile."""
    replies = {}
    for line in (TOOL_TEST / "calls.jsonl").read_text().splitlines():
        call = json.loads(line)
        replies[call["frame"], call["tile"]] = call["answer"]["response"]
    return replies


class ToolTestFlight(unittest.TestCase):
    """The four-frame tool test, replayed from Ember's recorded replies."""

    @classmethod
    def setUpClass(cls):
        cls.folder = TemporaryDirectory()
        flight = write_flight(Path(cls.folder.name) / "flight", TOOL_TEST_SIZES)
        cls.out = Path(cls.folder.name) / "results"
        cls.status, cls.printed = run_command([str(flight), "--out", str(cls.out)], SimulatedEmber(recorded_replies()))
        cls.record = json.loads((cls.out / "search-record.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_reviewer_queue_coverage_map_and_report_page_match_todays_output(self):
        self.assertEqual((self.out / "queue.json").read_text(), (TOOL_TEST / "queue.json").read_text())
        self.assertEqual((self.out / "coverage.json").read_text(), (TOOL_TEST / "coverage.json").read_text())
        self.assertEqual((self.out / "report.html").read_text(),
                         (Path(__file__).parent / "fixtures" / "tool-test" / "report.html").read_text())

    def test_search_record_holds_every_tile_of_every_frame(self):
        timeline = self.record["coverage_timeline"]
        self.assertEqual([frame["frame"] for frame in timeline], ["frame-01", "frame-02", "frame-03", "frame-04"])
        statuses = {frame["frame"]: [tile["status"] for tile in frame["tiles"]] for frame in timeline}
        not_checked = "not checked"
        self.assertEqual(statuses["frame-01"], [not_checked, not_checked, not_checked, "checked, no sighting", "flagged",
                                                not_checked, not_checked, not_checked, not_checked])
        self.assertEqual(statuses["frame-04"], [not_checked, not_checked, "flagged", not_checked, not_checked,
                                                "checked, no sighting", not_checked, not_checked, not_checked])

    def test_search_record_holds_every_possible_sighting_in_frame_pixels(self):
        sightings = self.record["sightings"]
        # frame-03 has seven marks. The reviewer queue keeps five of them; the record keeps all.
        self.assertEqual(len(sightings), 15)
        self.assertEqual(sum(s["frame"] == "frame-03" for s in sightings), 7)
        first = sightings[0]
        self.assertEqual((first["frame"], first["tile"], first["confidence"]), ("frame-01", 4, 0.9))
        self.assertAlmostEqual(first["x"], 1446.4)
        self.assertAlmostEqual(first["y"], 986.4)

    def test_search_record_holds_every_call_with_its_tokens_and_cost(self):
        calls = self.record["calls"]
        self.assertEqual(len(calls), 12)
        self.assertEqual(sum(call["usage"]["input_tokens"] for call in calls), 7632)
        self.assertEqual(sum(call["usage"]["output_tokens"] for call in calls), 3116)
        self.assertEqual(sum(call["paid_nanodollars"] for call in calls), 2321200)
        self.assertEqual(self.record["spent_nanodollars"], 2321200)

    def test_search_record_says_the_run_finished(self):
        self.assertEqual(self.status, 0)
        self.assertEqual(self.record["ending"], {"outcome": "finished", "reason": None})
        self.assertIn("4 frames, 13 sightings, $0.0023 spent. Finished.", self.printed)


class ScriptedFlight(unittest.TestCase):
    """Two 300 x 200 frames. Each simulated reply costs 700 input and 100 output tokens: $0.00012.
    The worst case reserved before each request is 700 input and 2,000 output tokens: $0.00107."""

    def search(self, replies, *options):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200), (300, 200)])
        out = Path(folder.name) / "results"
        status, printed = run_command([str(flight), "--out", str(out), *options], SimulatedEmber(replies))
        return status, printed, json.loads((out / "search-record.json").read_text()), out

    def statuses(self, record, frame):
        return [tile["status"] for tile in record["coverage_timeline"][frame]["tiles"]]

    def test_a_stop_at_the_spending_cap_says_so_and_exits_normally(self):
        replies = {("frame-01", -1): '{"tiles":[4,0]}', ("frame-02", -1): '{"tiles":[4,0]}',
                   ("frame-01", 4): '{"points":[[0.5,0.5,0.9]]}', ("frame-02", 4): "[]",
                   ("frame-01", 0): "[]", ("frame-02", 0): "[]"}
        status, printed, record, _ = self.search(replies, "--budget", "0.0015", "--looks", "2")
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"], {"outcome": "spending cap",
                                            "reason": "the next request could have exceeded the budget"})
        self.assertIn("Stopped early", printed)
        # Four requests fit: after them, $0.00048 spent plus a $0.00107 worst case would cross the $0.0015 cap.
        self.assertEqual(len(record["calls"]), 4)
        self.assertEqual(record["spent_nanodollars"], 480_000)
        self.assertEqual(record["settings"]["spending_cap_nanodollars"], 1_500_000)
        self.assertEqual(self.statuses(record, 0)[:5], ["not checked", "not checked", "not checked", "not checked", "flagged"])
        sighting = record["sightings"][0]
        self.assertEqual((sighting["frame"], sighting["tile"], sighting["x"], sighting["y"]), ("frame-01", 4, 150, 99.5))

    def test_a_failed_request_writes_the_record_and_exits_with_status_1(self):
        replies = {("frame-01", -1): '{"tiles":[4,0]}', ("frame-02", -1): '{"tiles":[4,0]}',
                   ("frame-01", 4): '{"points":[[0.5,0.5,0.9]]}',
                   ("frame-02", 4): ConnectionResetError("simulated reset")}
        status, printed, record, out = self.search(replies)
        self.assertEqual(status, 1)
        self.assertEqual(record["ending"], {"outcome": "failed", "reason": "ConnectionResetError: simulated reset"})
        self.assertIn("Stopped early: ConnectionResetError: simulated reset", printed)
        self.assertEqual([(call["frame"], call["tile"]) for call in record["calls"]],
                         [("frame-01", -1), ("frame-02", -1), ("frame-01", 4)])
        self.assertEqual(record["spent_nanodollars"], 360_000)
        self.assertEqual([s["frame"] for s in record["sightings"]], ["frame-01"])
        self.assertEqual(self.statuses(record, 1)[4], "not checked")
        self.assertTrue((out / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
