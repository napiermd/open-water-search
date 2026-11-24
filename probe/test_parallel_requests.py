"""#3: requests run in parallel within Meta's rate limits, and the spending cap still holds.

    python3 -m unittest discover -s probe
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from open_water_search import RateLimited
from simulated_ember import SimulatedEmber, frame_name, run_command, write_flight


def frames_of(count):
    return [frame_name(index) for index in range(count)]


def quiet_flight(count):
    """Replies for a flight of count frames: every overview ranks tile 4 then tile 0, and no close look finds anyone."""
    replies = {}
    for name in frames_of(count):
        replies[name, -1] = '{"tiles":[4,0]}'
        replies[name, 4] = "[]"
        replies[name, 0] = "[]"
    return replies


class ParallelFlight(unittest.TestCase):
    """300 x 200 frames. Each simulated reply costs 700 input and 100 output tokens: $0.00012.
    The worst case reserved before each request is 700 input and 2,000 output tokens: $0.00107."""

    def search(self, count, ember, *options):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200)] * count)
        out = Path(folder.name) / "results"
        status, printed = run_command([str(flight), "--out", str(out), *options], ember)
        return status, printed, json.loads((out / "search-record.json").read_text()), out

    def requests_in(self, record):
        return [(call["frame"], call["tile"]) for call in record["calls"]]

    def test_eight_requests_run_at_once_and_the_record_keeps_search_order(self):
        names = frames_of(16)
        # Every overview takes 0.25 s, and frame-01's takes longest, so it finishes after later frames.
        latency = {(name, -1): 0.25 for name in names}
        latency["frame-01", -1] = 0.6
        ember = SimulatedEmber(quiet_flight(16), latency)
        status, _, record, _ = self.search(16, ember, "--looks", "1")
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"], {"outcome": "finished", "reason": None})
        self.assertEqual(ember.most_in_flight, 8)
        self.assertEqual(record["settings"]["parallel"], 8)
        self.assertEqual(self.requests_in(record), [(name, -1) for name in names] + [(name, 4) for name in names])
        # One at a time the overviews alone take 4.35 s, about 220 photos a minute. Eight at once take at
        # least 0.75 s, so no more than 1,280 photos a minute.
        self.assertGreater(record["photos_per_minute"], 600)
        self.assertLessEqual(record["photos_per_minute"], 1280)

    def test_the_number_of_requests_at_once_is_configurable(self):
        latency = {(name, -1): 0.1 for name in frames_of(4)}
        ember = SimulatedEmber(quiet_flight(4), latency)
        status, _, record, _ = self.search(4, ember, "--looks", "0", "--parallel", "2")
        self.assertEqual(status, 0)
        self.assertEqual(ember.most_in_flight, 2)
        self.assertEqual(record["settings"]["parallel"], 2)

    def test_parallel_requests_never_cross_the_spending_cap_together(self):
        names = frames_of(8)
        latency = {(name, tile): 0.1 for name in names for tile in (-1, 4, 0)}
        ember = SimulatedEmber(quiet_flight(8), latency)
        status, printed, record, _ = self.search(8, ember, "--budget", "0.0035", "--looks", "2")
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"]["outcome"], "spending cap")
        # Three $0.00107 worst cases fit under the $0.0035 cap and a fourth does not, so at most three requests
        # are in flight. What was paid plus the worst case of every request in flight never crosses the cap.
        self.assertEqual(ember.most_in_flight, 3)
        self.assertLessEqual(ember.most_committed, 3_500_000)
        # As when requests run one at a time: after 21 requests, $0.00252 spent plus a $0.00107 worst case
        # would cross the cap. They are the overviews, the first round of close looks, then frames 1 to 5.
        self.assertEqual(self.requests_in(record), [(name, -1) for name in names] + [(name, 4) for name in names]
                         + [(name, 0) for name in names[:5]])
        self.assertEqual(record["spent_nanodollars"], 2_520_000)

    def test_a_429_waits_at_least_retry_after_then_backs_off_with_jitter(self):
        replies = quiet_flight(2)
        replies["frame-01", -1] = [RateLimited(None), RateLimited(1), '{"tiles":[4,0]}']
        ember = SimulatedEmber(replies)
        status, _, record, _ = self.search(2, ember, "--looks", "0", "--retries", "2")
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"], {"outcome": "finished", "reason": None})
        self.assertEqual(self.requests_in(record), [("frame-01", -1), ("frame-02", -1)])
        first, second, third = ember.times_sent(("frame-01", -1))
        # The first back-off is 500 ms with up to 50% jitter either way. The second doubles, after Retry-After.
        self.assertGreaterEqual(second - first, 0.25)
        self.assertLess(second - first, 1.0)
        self.assertGreaterEqual(third - second, 1 + 0.5)

    def test_by_default_a_request_is_retried_once_after_a_429_and_a_second_429_fails_the_run(self):
        replies = quiet_flight(2)
        replies["frame-01", -1] = [RateLimited(None), RateLimited(None), '{"tiles":[4,0]}']
        ember = SimulatedEmber(replies)
        status, _, record, _ = self.search(2, ember, "--looks", "0")
        self.assertEqual(status, 1)
        self.assertEqual(record["ending"]["outcome"], "failed")
        self.assertEqual(len(ember.times_sent(("frame-01", -1))), 2)
        self.assertEqual(record["settings"]["retries"], 1)

    def test_a_timeout_is_retried_once_and_the_run_carries_on(self):
        replies = quiet_flight(2)
        replies["frame-01", -1] = [TimeoutError("The read operation timed out"), '{"tiles":[4,0]}']
        ember = SimulatedEmber(replies)
        status, _, record, _ = self.search(2, ember, "--looks", "0")
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"], {"outcome": "finished", "reason": None})
        self.assertEqual(len(ember.times_sent(("frame-01", -1))), 2)
        self.assertEqual(record["coverage_timeline"][0]["overview"], "done")

    def test_a_request_lost_on_every_try_leaves_only_its_overview_unreadable(self):
        replies = quiet_flight(3)
        replies["frame-02", -1] = TimeoutError("The read operation timed out")
        ember = SimulatedEmber(replies)
        status, printed, record, _ = self.search(3, ember, "--looks", "1")
        self.assertEqual(status, 0)
        self.assertEqual(record["ending"], {"outcome": "finished", "reason": None})
        self.assertEqual([frame["overview"] for frame in record["coverage_timeline"]], ["done", "unreadable", "done"])
        lost = [call for call in record["calls"] if call["frame"] == "frame-02"]
        self.assertEqual(len(lost), 1)
        self.assertIn("request lost after 2 tries: TimeoutError", lost[0]["answer"]["failure"])
        self.assertIs(lost[0]["answer"]["lost"], True)
        # A lost request may still be billed, so its worst case counts toward what was spent.
        self.assertGreater(lost[0]["paid_nanodollars"], 0)
        self.assertEqual(record["spent_nanodollars"], sum(call["paid_nanodollars"] for call in record["calls"]))

    def test_ten_lost_requests_in_a_row_end_the_run(self):
        replies = quiet_flight(12)
        for name in frames_of(12):
            replies[name, -1] = ConnectionResetError("simulated reset")
        status, _, record, _ = self.search(12, SimulatedEmber(replies), "--looks", "0", "--parallel", "1")
        self.assertEqual(status, 1)
        self.assertEqual(record["ending"], {"outcome": "failed", "reason": "RuntimeError: 10 unreadable answers in a row"})

    def test_low_rate_limit_headers_space_requests_out(self):
        # 200 requests left of 3,000 a minute is under a tenth, so requests are spaced 60 s / 200 = 0.3 s apart.
        limits = dict(limit_requests=3000, remaining_requests=200, limit_tokens=4_000_000, remaining_tokens=3_000_000)
        ember = SimulatedEmber(quiet_flight(3), limits=limits)
        status, _, _, _ = self.search(3, ember, "--looks", "0")
        self.assertEqual(status, 0)
        times = sorted(when for when, _ in ember.sent)
        # The simulated Ember notes the time after reading the image, so allow a few milliseconds of thread jitter.
        self.assertGreaterEqual(min(later - earlier for earlier, later in zip(times, times[1:])), 0.29)

    def test_a_failed_request_among_parallel_ones_writes_the_record_and_exits_with_status_1(self):
        names = frames_of(6)
        replies = quiet_flight(6)
        replies["frame-03", -1] = PermissionError("simulated refusal")
        # frame-03 fails after every other overview has been answered.
        latency = {(name, -1): 0.1 for name in names}
        latency["frame-03", -1] = 0.3
        status, printed, record, out = self.search(6, SimulatedEmber(replies, latency), "--looks", "1")
        self.assertEqual(status, 1)
        self.assertEqual(record["ending"], {"outcome": "failed", "reason": "PermissionError: simulated refusal"})
        self.assertIn("Stopped early: PermissionError: simulated refusal", printed)
        self.assertEqual(self.requests_in(record), [(name, -1) for name in names if name != "frame-03"])
        self.assertEqual(record["spent_nanodollars"], 5 * 120_000)
        self.assertTrue((out / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
