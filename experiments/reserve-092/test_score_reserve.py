import fcntl
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import score_reserve as s


def frame(second, flags, video=s.DOMINANT, block="first"):
    return dict(frame=f"{video}-{second}", second=second, video=video, video_frame=second * 30,
                width=100, height=100, image=f"{second}.jpg", block=block, flags=flags)


def verdict(job, i=0, yes=True, confidence=.92):
    return dict(frame=job, arm="current", i=i, yes=yes, confidence=confidence,
                what="fixture", nearby=False)


def database(folder, calls, manifest="inputs", stop=None):
    db = sqlite3.connect(folder / "ledger.sqlite")
    with db:
        db.execute("CREATE TABLE settings (id INTEGER, manifest TEXT, stop TEXT)")
        db.execute("INSERT INTO settings VALUES (1,?,?)", (manifest, stop))
        db.execute("CREATE TABLE calls (arm TEXT, frame TEXT, i INTEGER, reserved INTEGER, paid INTEGER, result TEXT)")
        db.executemany("INSERT INTO calls VALUES (?,?,?,?,?,?)", calls)
    db.close()


class ReserveTests(unittest.TestCase):
    def test_threshold_identity_scope_duplicate_marks_and_exposure_gaps(self):
        true_box, false_box = [0, 0, 2, 2, .8], [72, 72, 74, 74, .7]
        other = sorted(s.VIDEOS - {s.DOMINANT})[0]
        frames = [frame(i, [false_box]) for i in range(4)]
        frames += [frame(4, [false_box], block="next"), frame(5, [], block="next"),
                   frame(3, [true_box], video=other)]
        additions = [dict(f, flags=[true_box, true_box, false_box], tile_indices=[2, 3, 5])
                     if f["video"] == s.DOMINANT and f["second"] in (0, 1, 2, 3)
                     else dict(f, flags=[], tile_indices=[]) for f in frames]
        truth = {f["frame"]: [(0, [0, 0, 2, 2], False)] for f in frames}
        charges, decisions = {}, {}
        for f, more in zip(frames, additions):
            for source, row in (("whole", f), ("tile", more)):
                job = f"{source}/{f['frame']}"
                if not row["flags"]:
                    continue
                charges[job] = {"status": "usable"}
                for i in range(len(row["flags"])):
                    decisions[job, i] = verdict(job, i, confidence=.01 if source == "whole" else .92)
        charges["tile/" + frames[1]["frame"]]["status"] = "unusable"
        for f in (frames[2], frames[3]):
            for i in range(3):
                decisions["tile/" + f["frame"], i]["confidence"] = .9199
        decisions["tile/" + frames[0]["frame"], 2]["yes"] = False
        r = s.score(frames, additions, truth, charges, decisions)
        self.assertEqual((7, 6), (r["eligible_frames"], r["paired_frames"]))
        self.assertEqual([{"frame": frames[1]["frame"], "jobs": {"tile": "unusable"}}], r["omitted_frames"])
        all_counts = r["totals"]["all"]
        self.assertEqual((1, 2), (all_counts["baseline"]["found"], all_counts["combined"]["found"]))
        self.assertEqual(4, all_counts["combined"]["false_marks"])
        self.assertEqual(4, all_counts["combined"]["false_mark_seconds"])
        self.assertEqual(3, all_counts["combined"]["false_episodes"])
        self.assertEqual((2, 1), (all_counts["delta"]["true_marks"], all_counts["delta"]["person_seconds"]))
        self.assertEqual(0, r["totals"]["excluding_dominant"]["delta"]["found"])
        gained, = r["added_ids"]
        self.assertEqual((s.DOMINANT, 0), (gained["video"], gained["track_id"]))
        self.assertEqual([frames[0]["frame"]], gained["frames"])
        self.assertEqual([0, 1], [m["i"] for m in gained["marks"]])
        self.assertEqual([2, 3], [m["tile_rank_index"] for m in gained["marks"]])

    def test_reserve_truth_uses_real_names_and_keeps_pilot_guard(self):
        f = frame(1, [])
        im = dict(id=1, file_name=Path(s.DOMINANT).stem + "_000030.PNG", width=100, height=100)
        ann = dict(image_id=1, category_id=1, bbox=[0, 0, 5, 5])
        coco = dict(images=[im, dict(id=2, file_name="other.PNG")],
                    annotations=[ann, dict(ann, attributes={"track_id": 0}), dict(image_id=2)])
        exc = [dict(video=s.DOMINANT, second=1, track_id=0)]
        truth, audit = s.load_reserve_truth([f], coco, exc)
        self.assertTrue(all(row[2] for row in truth[f["frame"]]))
        self.assertEqual((1, 1), (audit["missing_track_boxes"], audit["land_boxes"]))
        with self.assertRaisesRegex(ValueError, "Outside pilot"):
            s.pilot.load_truth([f], coco, exc)
        with self.assertRaisesRegex(ValueError, "Unmatched land"):
            s.load_reserve_truth([f], coco, [dict(exc[0], second=2)])

    def test_reconcile_partial_and_cap(self):
        jobs = {k: [[0]] for k in ("whole/a", "tile/a", "whole/b", "tile/b")}
        row = verdict("whole/a")
        calls = [("current", "whole/a", -1, 100, 70, json.dumps([row])),
                 ("current", "tile/a", -1, 100, 0, None),
                 ("current", "whole/b", -1, 80, None, None)]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            database(folder, calls, stop="breaker")
            (folder / "verdicts.jsonl").write_text(json.dumps(row) + "\n")
            charges, decisions, cost = s.reconcile(folder, jobs, "inputs")
            self.assertEqual(set(s.STATUSES), {c["status"] for c in charges.values()})
            self.assertEqual({("whole/a", 0): row}, decisions)
            self.assertEqual((70, 80, 150, "breaker"), tuple(cost[k] for k in
                             ("paid_nanodollars", "unresolved_reserved_nanodollars",
                              "maximum_liability_nanodollars", "ledger_stop")))
            with patch.object(s, "CAP", 149), self.assertRaisesRegex(ValueError, "cap exceeded"):
                s.reconcile(folder, jobs, "inputs")
            with self.assertRaisesRegex(ValueError, "manifest mismatch"):
                s.reconcile(folder, jobs, "different")
            (folder / "verdicts.jsonl").write_text(json.dumps(dict(row, yes=False)))
            with self.assertRaisesRegex(ValueError, "disagree"):
                s.reconcile(folder, jobs, "inputs")

    def test_rejects_wrong_jobs_indices_bills_and_partial_batches(self):
        job = "tile/a"
        row = verdict(job)
        valid = ("current", job, -1, 12, 8, json.dumps([row]))
        bad_calls = [("padded", *valid[1:]), ("current", "whole/a", *valid[2:]),
                     (*valid[:2], 0, *valid[3:]), (*valid[:4], 13, valid[5]),
                     (*valid[:4], None, valid[5]), (*valid[:5], "[]"),
                     (*valid[:5], json.dumps([dict(row, i=True)])),
                     (*valid[:5], json.dumps([dict(row, frame="whole/a")]))]
        for call in bad_calls:
            with self.subTest(call=call), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                database(folder, [call])
                (folder / "verdicts.jsonl").write_text("")
                with self.assertRaises(ValueError):
                    s.reconcile(folder, {job: [[0]]}, "inputs")

    def test_busy_directory_refuses_before_opening_any_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fd = os.open(folder, os.O_RDONLY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                with self.assertRaisesRegex(ValueError, "busy"):
                    s.run(folder, folder / "annotations", "x")
            finally:
                os.close(fd)

    def test_manifest_includes_empty_jobs_in_round_robin_order(self):
        a, b = frame(0, []), frame(1, [[0]])
        c = frame(0, [[1]], sorted(s.VIDEOS - {s.DOMINANT})[0])
        frames = [a, b, c]
        more = [dict(f, flags=[]) for f in frames]
        jobs = [dict(f, frame=prefix + f["frame"], flags=f["flags"] if prefix == "whole/" else [])
                for f in (a, c, b) for prefix in ("whole/", "tile/")]
        self.assertEqual(2, len(s.expected_jobs(frames, more, jobs)))
        for bad in (jobs[:-1], jobs[::-1], [*jobs[:3], jobs[0], *jobs[4:]]):
            with self.assertRaises(ValueError):
                s.expected_jobs(frames, more, bad)

    def test_seal_replay_checks_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            args = (folder, {}, {"complete": False}, {"inputs.json": "fixture"}, "truth")
            s.publish(*args)
            s.publish(*args)
            seal = s.read(folder / "seal.json")
            self.assertEqual(s.digest(folder / "summary.json"), seal["sha256"]["summary.json"])
            (folder / "summary.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Existing result seal"):
                s.publish(*args)


if __name__ == "__main__":
    unittest.main()
