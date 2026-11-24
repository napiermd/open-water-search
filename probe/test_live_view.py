"""#16: the fixed method prints each decision as its answer arrives, so a live run shows the search happening.

    python3 -m unittest discover -s probe
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from simulated_ember import SimulatedEmber, run_command, write_flight


class LiveView(unittest.TestCase):
    def test_each_overview_and_close_look_prints_one_line_as_it_is_answered(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200), (300, 200)])
        ember = SimulatedEmber({
            ("frame-01", -1): '{"tiles":[4,0]}',
            ("frame-01", 4): json.dumps({"points": [{"x": 500, "y": 500, "confidence": 0.9}]}),
            ("frame-01", 0): json.dumps({"points": []}),
            ("frame-02", -1): "not json",
        })
        status, printed = run_command([str(flight), "--out", str(Path(folder.name) / "out"), "--looks", "2",
                                       "--parallel", "1", "--format", "grounding"], ember)
        self.assertEqual(status, 0)
        lines = printed.splitlines()
        for expected in ("frame-01: overview ranks the center first, then the top left",
                         "frame-01: close look at the center: 1 possible person, confidence 0.90",
                         "frame-01: close look at the top left: no one marked",
                         "frame-02: overview: unreadable"):
            self.assertIn(expected, lines)
        # Decisions come before the handoff messages and the closing summary.
        self.assertLess(lines.index("frame-01: close look at the center: 1 possible person, confidence 0.90"),
                        len(lines) - 1)

    def test_the_search_record_logs_every_printed_decision_with_its_frame_tile_and_time(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200), (300, 200)])
        out = Path(folder.name) / "out"
        ember = SimulatedEmber({
            ("frame-01", -1): '{"tiles":[4,0]}',
            ("frame-01", 4): json.dumps({"points": [{"x": 500, "y": 500, "confidence": 0.9}]}),
            ("frame-01", 0): TimeoutError("The read operation timed out"),
            ("frame-02", -1): "not json",
        })
        status, printed = run_command([str(flight), "--out", str(out), "--looks", "2", "--parallel", "1",
                                       "--format", "grounding"], ember)
        self.assertEqual(status, 0)
        record = json.loads((out / "search-record.json").read_text())
        log = record["decision_log"]
        self.assertEqual([(entry["frame"], entry["tile"], entry["text"]) for entry in log], [
            ("frame-01", None, "frame-01: overview ranks the center first, then the top left"),
            ("frame-02", None, "frame-02: overview: unreadable"),
            ("frame-01", 4, "frame-01: close look at the center: 1 possible person, confidence 0.90"),
            ("frame-01", 0, "frame-01: close look at the top left: request lost after 2 tries: TimeoutError: "
                            "The read operation timed out")])
        # Printing stays as it was: the same lines, in the same order, before the handoff messages.
        self.assertEqual(printed.splitlines()[:4], [entry["text"] for entry in log])
        seconds = [entry["seconds"] for entry in log]
        self.assertEqual(seconds, sorted(seconds))
        self.assertGreaterEqual(seconds[0], 0)
        self.assertLessEqual(seconds[-1], record["seconds"])


if __name__ == "__main__":
    unittest.main()
