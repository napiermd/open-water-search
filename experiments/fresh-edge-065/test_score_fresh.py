"""All evidence in these tests is generated locally. No runner or provider is invoked."""
from contextlib import closing
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import score_fresh as s


def frame(video, second, flags):
    return dict(frame=f"{video}-{second}", video=video, second=second, video_frame=30 * second,
                block="first", width=400, height=200, flags=flags)


def edge(row, indices):
    return dict(row, original_indices=indices, flags=[row["flags"][i] for i in indices])


def pair(row, subset):
    return [dict(row, frame="whole/" + row["frame"]), dict(subset, frame="edge/" + row["frame"])]


def decision(job, i, yes=True, confidence=.01):
    return dict(arm="current", frame=job, i=i, yes=yes, confidence=confidence, what="fixture", nearby=False)


def write(path, obj):
    path.write_text(json.dumps(obj) + "\n")


def evidence(folder, calls, manifest, stop=None):
    exported = []
    with closing(sqlite3.connect(folder / "ledger.sqlite")) as db, db:
        db.execute("CREATE TABLE settings (id INTEGER, manifest TEXT, stop TEXT)")
        db.execute("INSERT INTO settings VALUES (1,?,?)", (manifest, stop))
        db.execute("CREATE TABLE calls (arm TEXT, frame TEXT, i INTEGER, reserved INTEGER, paid INTEGER, result TEXT)")
        for job, reserved, paid, rows in calls:
            db.execute("INSERT INTO calls VALUES ('current',?,-1,?,?,?)",
                       (job, reserved, paid, json.dumps(rows) if rows is not None else None))
            exported.extend(rows or [])
    (folder / "verdicts.jsonl").write_text("".join(json.dumps(v) + "\n" for v in reversed(exported)))


class FreshScoring(unittest.TestCase):
    def folder(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name) / "experiments" / "fresh-edge-065"
        folder.mkdir(parents=True)
        return folder

    def test_end_to_end_replacement_id_comparison_and_seal(self):
        folder = self.folder()
        # Original indices 0, 2, 3 are edge flags. Index 1 stays shared even at .01.
        boxes = [[i, 0, i + 2, 2, .9] for i in (0, 100, 200, 300)]
        a = frame("A.mp4", 0, boxes)
        b = frame("A.mp4", 1, [boxes[1], boxes[1]])
        c = frame("B.mp4", 0, [])
        frames = [a, b, c]
        edges = [edge(a, [0, 2, 3]), edge(b, []), edge(c, [])]
        inputs = pair(a, edges[0]) + pair(c, edges[2]) + pair(b, edges[1])
        coco = dict(images=[], annotations=[])
        for image_id, (f, tracks) in enumerate(zip(frames, [[1, 2, 3, 4, 5], [2], [1]])):
            coco["images"].append(dict(id=image_id, file_name=f"{Path(f['video']).stem}_{f['video_frame']:06}.PNG",
                                       width=f["width"], height=f["height"]))
            for track in tracks:
                x = (track - 1) * 100 if track < 5 else 50
                coco["annotations"].append(dict(image_id=image_id, category_id=1, bbox=[x, 0, 3, 3],
                                                attributes={"track_id": track}))
        for name, obj in [("fresh.json", frames), ("edges.json", edges), ("inputs.json", inputs),
                          ("truth.json", coco), ("exclusions.json", [dict(video=a["video"], second=0, track_id=5)])]:
            write(folder / name, obj)
        for name in s.REQUIRED | {"PLAN.md"}:
            path = folder / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                if name in (s.PILOT_SOURCE, s.PROBE_SOURCE):
                    path.write_bytes((s.HERE / name).read_bytes())
                else:
                    path.write_text("fixture")
        pins = {n: s.digest(folder / n) for n in s.PINNED}
        hashes = {n: s.digest(folder / n) for n in sorted(s.REQUIRED | pins.keys())}
        write(folder / "lock.json", hashes)
        whole, padded = inputs[0]["frame"], inputs[1]["frame"]
        other = inputs[-2]["frame"]
        calls = [(whole, 20, 10, [decision(whole, i, i != 2) for i in range(4)]),
                 (padded, 20, 11, [decision(padded, 0, False, 1), decision(padded, 1, True, .65),
                                   decision(padded, 2, True, .649999)]),
                 (other, 20, 12, [decision(other, i) for i in range(2)])]
        evidence(folder, calls, pins["inputs.json"])
        lock_sha = s.digest(folder / "lock.json")
        annotation_hash = s.digest(folder / "truth.json")
        with patch.object(s, "PINNED", pins), patch.object(s, "ANNOTATIONS_SHA", annotation_hash):
            def replay():
                return s.run(folder, folder / "truth.json", lock_sha)
            summary = replay()
            self.assertEqual(summary, replay())
            self.assertTrue(summary["complete"])
            self.assertEqual(3, summary["paired_frames"])
            self.assertFalse(summary["current_found_everyone_on_paired"])
            self.assertEqual(1, summary["full_manifest_track_audit"]["land_boxes"])
            people = {(p["video"], p["track_id"]): (p["current_hit_seconds"], p["padded_edge_hit_seconds"])
                      for p in summary["identities"]}
            self.assertEqual({("A.mp4", 1): ([0], []), ("A.mp4", 2): ([0, 1], [0, 1]),
                              ("A.mp4", 3): ([], [0]), ("A.mp4", 4): ([0], []),
                              ("B.mp4", 1): ([], [])}, people)
            self.assertEqual([dict(video="A.mp4", track_id=3)], summary["gained_ids"])
            self.assertEqual([dict(video="A.mp4", track_id=i) for i in (1, 4)], summary["lost_ids"])
            self.assertEqual((4, 3), tuple(summary["totals"][arm]["person_seconds"] for arm in ("current", "padded_edge")))
            self.assertEqual(4, summary["totals"]["padded_edge"]["true_marks"])
            self.assertEqual(1, summary["by_clip"]["B.mp4"]["current"]["missed"])
            self.assertEqual(33, summary["accounting"]["paid_nanodollars"])
            seal = s.read(folder / "seal.json")
            self.assertEqual(annotation_hash, seal["annotations_sha256"])
            for name, sha in seal["sha256"].items():
                self.assertEqual(sha, s.digest(folder / name))
            self.assertEqual(3, len(s.read(folder / "charges.json")))
            self.assertNotIn("A.mp4", s.pilot.VIDEOS)
            for name in sorted(s.REQUIRED | pins.keys()):
                path = folder / name
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.subTest(tampered=name), self.assertRaisesRegex(ValueError, "Locked file changed"):
                    replay()
                path.write_bytes(original)
            (folder / "truth.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Wrong COCO annotations"):
                replay()
            write(folder / "truth.json", coco)
            (folder / "summary.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Existing result seal"):
                replay()

    def test_partial_coverage_breaks_episodes_and_omits_unobserved_ids(self):
        box = [0, 0, 2, 2, .8]
        frames = [frame("A.mp4", i, [box]) for i in range(5)] + [frame("B.mp4", 7, [])]
        edges = [edge(f, [0] if f["flags"] else []) for f in frames]
        truth = {f["frame"]: [] for f in frames}
        truth[frames[1]["frame"]] = [(7, [0, 0, 2, 2], False)]
        charges, decisions = {}, {}
        for f, e in zip(frames[:-1], edges):
            for job in pair(f, e):
                name = job["frame"]
                charges[name] = {"status": "usable"}
                decisions[name, 0] = decision(name, 0, confidence=.9)
        charges["edge/" + frames[1]["frame"]]["status"] = "unresolved"
        charges["whole/" + frames[4]["frame"]]["status"] = "unattempted"
        result = s.score(frames, edges, truth, charges, decisions)
        self.assertEqual((6, 4), (result["eligible_frames"], result["paired_frames"]))
        self.assertEqual([{"edge": "unresolved"}, {"whole": "unattempted"}],
                         [f["jobs"] for f in result["omitted_frames"]])
        self.assertEqual([], result["identities"])
        self.assertIsNone(result["current_found_everyone_on_paired"])
        for arm in ("current", "padded_edge"):
            for c in [result["by_clip"]["A.mp4"][arm], result["totals"][arm]]:
                self.assertEqual((3, 3, 2), (c["false_marks"], c["false_mark_seconds"], c["false_episodes"]))
                self.assertEqual(0, c["missed"])

    def test_round_robin_and_original_indices(self):
        a = frame("A", 0, [[1], [2]])
        b, c = frame("A", 1, []), frame("B", 0, [[3]])
        edges = [edge(a, [1]), edge(b, []), edge(c, [])]
        inputs = pair(a, edges[0]) + pair(c, edges[2]) + pair(b, edges[1])
        self.assertEqual({"whole/A-0": 2, "edge/A-0": 1, "whole/B-0": 1},
                         s.expected_jobs([a, b, c], edges, inputs))
        for bad in (inputs[::-1], inputs[:-1]):
            with self.assertRaises(ValueError):
                s.expected_jobs([a, b, c], edges, bad)
        for indices in ([0], [True], [2], [-1], [1, 1]):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                s.expected_jobs([a, b, c], [dict(edges[0], original_indices=indices), *edges[1:]], inputs)

    def test_charge_reconciliation_including_outstanding_reservations(self):
        folder = self.folder()
        row = decision("whole/a", 0)
        calls = [("whole/a", s.CAP, 20, [row]), ("edge/a", 10, 4, None),
                 ("whole/b", s.CAP - 24, None, None)]
        evidence(folder, calls, "inputs", "stopped")
        jobs = dict.fromkeys(("whole/a", "edge/a", "whole/b", "edge/b"), 1)
        charges, decisions, costs = s.reconcile(folder, jobs, "inputs")
        self.assertEqual({("whole/a", 0): row}, decisions)
        self.assertEqual(set(s.STATUSES), {c["status"] for c in charges.values()})
        self.assertEqual((24, s.CAP - 24, s.CAP, "stopped"), tuple(costs[k] for k in
                         ("paid_nanodollars", "unresolved_reserved_nanodollars", "maximum_liability_nanodollars",
                          "ledger_stop")))
        with self.assertRaisesRegex(ValueError, "manifest mismatch"):
            s.reconcile(folder, jobs, "other")
        with closing(sqlite3.connect(folder / "ledger.sqlite")) as db, db:
            db.execute("UPDATE calls SET reserved=reserved+1 WHERE paid IS NULL")
        with self.assertRaisesRegex(ValueError, "cap exceeded"):
            s.reconcile(folder, jobs, "inputs")

    def test_rejects_export_mismatches_and_invalid_batches(self):
        job = "edge/a"
        row = decision(job, 0)
        for rows, exported in [([row], []), ([row], [dict(row, yes=False)]), ([row], [row, row]),
                               ([row, row], [row, row]), ([], []), ([dict(row, i=True)], []),
                               ([dict(row, confidence=1.1)], []), ([dict(row, arm="padded")], []),
                               ([dict(row, frame="whole/a")], [])]:
            folder = self.folder()
            evidence(folder, [(job, 10, 7, rows)], "inputs")
            (folder / "verdicts.jsonl").write_text("".join(json.dumps(v) + "\n" for v in exported))
            with self.subTest(rows=rows, exported=exported), self.assertRaises(ValueError):
                s.reconcile(folder, {job: max(1, len(rows))}, "inputs")

    def test_lock_requires_manifests_and_external_sources_before_evidence(self):
        folder = self.folder()
        hashes = dict.fromkeys(s.REQUIRED | s.PINNED.keys(), "unused")
        for name in sorted(hashes):
            write(folder / "lock.json", {k: v for k, v in hashes.items() if k != name})
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Missing locked paths"):
                s.run(folder, folder / "absent", s.digest(folder / "lock.json"))
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            s.check_lock(folder, "incorrect")
        fd = os.open(folder, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            with self.assertRaisesRegex(ValueError, "busy"):
                s.run(folder, folder / "absent", "incorrect")
        finally:
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
