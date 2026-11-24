"""#6: in agent mode Ember runs the search through tool calls: look closer at a tile, report a sighting, and move
to the next frame.

    python3 -m unittest discover -s probe
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from open_water_search import AGENT_TOOLS, RateLimited
from runner import LIMIT, NANO, price
from simulated_ember import INPUT_TOKENS, SimulatedEmber, images_in, run_command, write_flight

MOVE_ON = ("move_to_next_frame", {})
# Each simulated reply costs 700 input and 100 output tokens. The worst case reserved before each agent request is
# Meta's count of 700 input tokens plus one token per character of the tool definitions, and 2,000 output tokens.
PAID = price(INPUT_TOKENS, 0, 100)
WORST = price(INPUT_TOKENS + len(json.dumps(AGENT_TOOLS)), 0, LIMIT)


def look(tile):
    return ("look_closer", {"tile": tile})


def report(tile, x, y, confidence):
    """A sighting at (x, y) on the 0-1,000 grid of the close look at tile."""
    return ("report_sighting", {"tile": tile, "x": x, "y": y, "confidence": confidence})


def budget(nanodollars):
    """The --budget argument for an exact budget in nanodollars."""
    dollars = f"{nanodollars / NANO:.9f}"
    assert round(float(dollars) * NANO) == nanodollars
    return dollars


def prompt(request):
    return next(part["text"] for part in request["input"][0]["content"] if part["type"] == "input_text")


class AgentMode(unittest.TestCase):
    """Fixture frames are 300 x 200. Tile 4, the center, spans x 100-200 and y 66-133."""

    def search(self, conversations, frames=1, *options):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200)] * frames)
        out = Path(folder.name) / "results"
        ember = SimulatedEmber({}, conversations=conversations)
        status, printed = run_command([str(flight), "--out", str(out), "--mode", "agent", *options], ember)
        record = json.loads((out / "search-record.json").read_text())
        return status, printed, record, ember

    def statuses(self, record, frame=0):
        return [tile["status"] for tile in record["coverage_timeline"][frame]["tiles"]]

    def test_ember_opens_a_tile_reports_a_sighting_and_moves_on_printing_each_tool_call(self):
        status, printed, record, _ = self.search({"frame-01": [[look(4)], [report(4, 500, 500, 0.9), MOVE_ON]]})
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"], {"outcome": "finished", "reason": None})
        self.assertEqual(record["settings"]["mode"], "agent")
        self.assertEqual(printed.splitlines()[:3], [
            "frame-01: look closer at the center tile (4)",
            "frame-01: report a sighting in the center tile (4) at x 150, y 100, confidence 0.90",
            "frame-01: move to the next frame"])
        sighting = record["sightings"][0]
        self.assertEqual((sighting["frame"], sighting["tile"], sighting["x"], sighting["y"], sighting["confidence"]),
                         ("frame-01", 4, 150, 99.5, 0.9))
        self.assertEqual(self.statuses(record), ["not checked"] * 4 + ["flagged"] + ["not checked"] * 4)
        self.assertEqual(len(record["calls"]), 2)

    def test_each_frame_gets_one_conversation_opening_with_its_overview_and_a_note_on_the_previous_frame(self):
        _, _, _, ember = self.search({"frame-01": [[look(4)], [report(4, 500, 500, 0.9), MOVE_ON]],
                                      "frame-02": [[look(0)], [MOVE_ON]],
                                      "frame-03": [[MOVE_ON]]}, 3)
        self.assertEqual([images_in(request) for request in ember.requests], [
            [("frame-01", -1)], [("frame-01", -1), ("frame-01", 4)],
            [("frame-02", -1)], [("frame-02", -1), ("frame-02", 0)],
            [("frame-03", -1)]])
        self.assertTrue(all(request["tools"] == AGENT_TOOLS for request in ember.requests))
        self.assertTrue(prompt(ember.requests[0]).endswith(" This is the first frame of the flight."))
        self.assertTrue(prompt(ember.requests[2]).endswith(
            " Previous frame: a sighting in the center tile at confidence 0.90, with close looks at 1 of 9 tiles."))
        self.assertTrue(prompt(ember.requests[4]).endswith(
            " Previous frame: no sightings, with close looks at 1 of 9 tiles."))

    def test_no_frame_takes_more_than_4_close_looks(self):
        status, printed, record, ember = self.search({"frame-01": [[look(0), look(1), look(2)], [look(3), look(4)],
                                                                   [MOVE_ON]]})
        self.assertEqual(status, 0)
        self.assertIn("frame-01: look closer at the center tile (4) refused: this frame has had its 4 close looks",
                      printed)
        self.assertEqual(self.statuses(record), ["checked, no sighting"] * 4 + ["not checked"] * 5)
        self.assertEqual(images_in(ember.requests[2])[1:], [("frame-01", tile) for tile in range(4)])

    def test_unused_share_of_the_budget_carries_forward_to_later_frames(self):
        # Each frame's share has room for one request and half of another. frame-01 moves on after one request, so
        # frame-02 can send three.
        share = WORST + PAID // 2
        status, printed, record, _ = self.search({"frame-01": [[MOVE_ON]],
                                                  "frame-02": [[look(0)], [look(1)], [MOVE_ON]],
                                                  "frame-03": [[MOVE_ON]]}, 3, "--budget", budget(3 * share))
        self.assertEqual(record["ending"], {"outcome": "finished", "reason": None})
        self.assertNotIn("share of the budget is spent", printed)
        self.assertEqual(self.statuses(record, 1)[:3], ["checked, no sighting"] * 2 + ["not checked"])
        self.assertEqual([call["frame"] for call in record["calls"]], ["frame-01"] + ["frame-02"] * 3 + ["frame-03"])

    def test_a_frame_ends_when_its_share_is_spent_and_the_search_moves_on(self):
        share = WORST + PAID // 2
        status, printed, record, ember = self.search({"frame-01": [[look(4)], [MOVE_ON]], "frame-02": [[MOVE_ON]]},
                                                     2, "--budget", budget(2 * share))
        self.assertEqual(record["ending"], {"outcome": "finished", "reason": None})
        self.assertIn("frame-01: its share of the budget is spent, so the search moves to the next frame", printed)
        # The close look at tile 4 never reached Ember, so that water stays unchecked.
        self.assertEqual(self.statuses(record, 0)[4], "not checked")
        self.assertEqual([images_in(request)[0] for request in ember.requests], [("frame-01", -1), ("frame-02", -1)])

    def test_a_frame_with_a_sighting_counts_as_covered_only_for_the_tiles_ember_received(self):
        status, printed, record, _ = self.search({"frame-01": [
            [look(4), report(4, 500, 500, 0.7)],
            [report(4, 500, 500, 0.9), report(2, 500, 500, 0.8), MOVE_ON]]})
        self.assertEqual(status, 0)
        refused = "refused: you have not received a close look at that tile"
        self.assertIn(f"frame-01: report a sighting in the center tile (4) {refused}", printed)
        self.assertIn(f"frame-01: report a sighting in the top right tile (2) {refused}", printed)
        self.assertEqual(self.statuses(record), ["not checked"] * 4 + ["flagged"] + ["not checked"] * 4)
        self.assertEqual([(s["tile"], s["confidence"]) for s in record["sightings"]], [(4, 0.9)])
        self.assertTrue(record["possible_people"][0]["handoff_message"].endswith(
            "8 of the 9 sections of that frame were never searched."))

    def test_the_spending_cap_counts_the_tool_definitions_that_metas_token_count_leaves_out(self):
        status, printed, record, ember = self.search({"frame-01": [[MOVE_ON]]}, 1,
                                                     "--budget", budget(price(INPUT_TOKENS, 0, LIMIT)))
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"]["outcome"], "spending cap")
        self.assertEqual(ember.requests, [])

    def test_a_run_stops_at_the_spending_cap_before_a_request_could_cross_it(self):
        status, printed, record, ember = self.search({"frame-01": [[look(4)], [MOVE_ON]]}, 1,
                                                     "--budget", budget(WORST + PAID // 2))
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"], {"outcome": "spending cap",
                                            "reason": "the next request could have exceeded the budget"})
        self.assertIn("Stopped early", printed)
        self.assertEqual(len(ember.requests), 1)
        self.assertEqual(record["spent_nanodollars"], PAID)
        # The close look at tile 4 never reached Ember, so that water stays unchecked.
        self.assertEqual(self.statuses(record, 0)[4], "not checked")

    def test_requests_go_one_at_a_time_through_the_rate_limit_retry_and_the_spending_cap_reservation(self):
        cap = 3 * WORST
        status, _, record, ember = self.search({"frame-01": [RateLimited(None), [look(4)], [MOVE_ON]],
                                                "frame-02": [[MOVE_ON]]}, 2, "--budget", budget(cap))
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"], {"outcome": "finished", "reason": None})
        self.assertEqual(len(ember.requests), 4)
        self.assertEqual(len(record["calls"]), 3)
        self.assertEqual(ember.most_in_flight, 1)
        self.assertLessEqual(ember.most_committed, cap)

    def test_the_fixed_two_look_method_stays_the_default(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200)])
        out = Path(folder.name) / "results"
        ember = SimulatedEmber({("frame-01", -1): '{"tiles":[4,0]}', ("frame-01", 4): "[]", ("frame-01", 0): "[]"})
        status, _ = run_command([str(flight), "--out", str(out)], ember)
        record = json.loads((out / "search-record.json").read_text())
        self.assertEqual(record["settings"]["mode"], "fixed")
        self.assertEqual([images_in(request) for request in ember.requests],
                         [[("frame-01", -1)], [("frame-01", 4)], [("frame-01", 0)]])
        self.assertFalse(any("tools" in request for request in ember.requests))


if __name__ == "__main__":
    unittest.main()
