"""Offline replay of the fresh edge-padding experiment locked at a672f12."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
import fcntl
import hashlib
from itertools import zip_longest
import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from types import FunctionType

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harder-pilot"))
import score_pilot as pilot

PINNED = {
    "PLAN.md": "64a616eff70b538df406e7ad9214ae34beb032b692ffbd257582f35309375faf",
    "fresh.json": "8265eabefbaa04b1ab723ec50f09283651768c6ba1b7a44b7d46c03e8a992d7d",
    "inputs.json": "7be38ddf6fe0233e93fb52b7638d77db2c514408a964baad9cbe6735c4a42c46",
}
ANNOTATIONS_SHA = "08b8050efec2972a98af831a17f691c09419674bc06e5876a5d004528cc2b0da"
PILOT_SOURCE = "../harder-pilot/score_pilot.py"
PROBE_SOURCE = "../../probe/score.py"
REQUIRED = {"edges.json", "exclusions.json", "audit.md", "select_windows.py", "run_fresh.py",
            "../tile-flag-check/run.py", "../harder-pilot/run_pilot.py", "../../probe/flag_check.py",
            "../edge-padding/edge.py", "../lost-people/flight-ranking/rank_flights.py",
            "../../probe/runner.py", "../../probe/open_water_search.py", PILOT_SOURCE, PROBE_SOURCE}
THRESHOLD = .65
CAP = 50_000_000  # nanodollars
STATUSES = ("usable", "unusable", "unresolved", "unattempted")
OUTPUTS = ("summary.json", "charges.json", "seal.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def read(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_keys)


def check_lock(folder, expected):
    raw = (folder / "lock.json").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, "Published lock.json SHA-256 mismatch")
    hashes = json.loads(raw, object_pairs_hook=unique_keys)
    require(isinstance(hashes, dict), "Expected a path-to-hash lock")
    missing = (REQUIRED | PINNED.keys()) - hashes.keys()
    require(not missing, f"Missing locked paths: {sorted(missing)}")
    for name, sha in hashes.items():
        require(digest(folder / name) == sha, f"Locked file changed: {name}")
    for name, sha in PINNED.items():
        require(hashes[name] == sha, f"Wrong preregistered file: {name}")
    for name, loaded in ((PILOT_SOURCE, pilot.__file__),
                         (PROBE_SOURCE, pilot.score_photo.__code__.co_filename)):
        require(digest(Path(loaded)) == hashes[name], f"Imported scorer differs from lock: {name}")
    require((folder / "audit.md").read_text().strip(), "Empty pre-call exclusion audit")
    return hashes


def expected_jobs(frames, edges, inputs):
    """Cross-check original indices, full job contents and the runner's dispatch order."""
    by_clip = defaultdict(list)
    seen = set()
    jobs = {}
    for f, e in zip(frames, edges, strict=True):
        name = f["frame"]
        require(name not in seen, f"Duplicate frame: {name}")
        seen.add(name)
        indices = e["original_indices"]
        require(isinstance(indices, list) and
                all(type(i) is int and 0 <= i < len(f["flags"]) for i in indices) and
                len(set(indices)) == len(indices), f"Invalid original indices: {name}")
        require(e == dict(f, original_indices=indices, flags=[f["flags"][i] for i in indices]),
                f"Edge subset differs from original: {name}")
        pair = [dict(row, frame=f"{source}/{name}") for source, row in (("whole", f), ("edge", e))]
        turns = by_clip[f["video"]]
        require(not turns or turns[-1][0]["second"] < f["second"], f"Unordered clip: {name}")
        turns.append(pair)
        jobs.update({row["frame"]: len(row["flags"]) for row in pair if row["flags"]})
    expected = [job for turn in zip_longest(*by_clip.values()) for pair in turn if pair for job in pair]
    require(inputs == expected, "Paired inputs differ from frozen frames or round-robin order")
    return jobs


def decision_key(row, job, count):
    i = row["i"]
    require(row["frame"] == job and row["arm"] == "current" and type(i) is int and 0 <= i < count,
            f"Invalid decision reference: {job}, {i}")
    require(type(row["yes"]) is bool and row["nearby"] is False and isinstance(row["what"], str)
            and type(row["confidence"]) in (int, float) and 0 <= row["confidence"] <= 1,
            f"Invalid verdict: {job}, {i}")
    return job, i


def reconcile(folder, jobs, manifest):
    charges = {job: dict(frame=job, arm="current", i=-1, reserved_nanodollars=0,
                         paid_nanodollars=None, status="unattempted") for job in sorted(jobs)}
    decisions = {}
    uri = (folder / "ledger.sqlite").as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("BEGIN")
        settings = db.execute("SELECT id, manifest, stop FROM settings").fetchall()
        require(len(settings) == 1 and settings[0][:2] == (1, manifest), "Ledger manifest mismatch")
        for arm, job, i, reserved, paid, result in db.execute(
                "SELECT arm, frame, i, reserved, paid, result FROM calls"):
            require(arm == "current" and i == -1 and job in jobs and
                    charges[job]["status"] == "unattempted", f"Unexpected ledger job: {job}")
            require(type(reserved) is int and 0 < reserved <= CAP and
                    (paid is None or type(paid) is int and 0 <= paid <= reserved),
                    f"Invalid charge: {job}")
            status = "unresolved" if paid is None else "unusable"
            if result is not None:
                rows = json.loads(result, object_pairs_hook=unique_keys)
                require(paid is not None and isinstance(rows, list) and len(rows) == jobs[job],
                        f"Unsettled or incomplete decision batch: {job}")
                for row in rows:
                    key = decision_key(row, job, jobs[job])
                    require(key not in decisions, f"Repeated decision: {key}")
                    decisions[key] = row
                status = "usable"
            charges[job].update(status=status, reserved_nanodollars=reserved, paid_nanodollars=paid)
    exported = {}
    with (folder / "verdicts.jsonl").open() as stream:
        for line in stream:
            row = json.loads(line, object_pairs_hook=unique_keys)
            job = row["frame"]
            require(job in jobs, f"Unexpected exported verdict: {job}")
            key = decision_key(row, job, jobs[job])
            require(key not in exported, f"Duplicate exported decision: {key}")
            exported[key] = row
    require(exported == decisions, "Verdicts disagree with ledger")
    paid = sum(c["paid_nanodollars"] or 0 for c in charges.values())
    reserved = sum(c["reserved_nanodollars"] for c in charges.values() if c["status"] == "unresolved")
    require(paid + reserved <= CAP, "Shared spending cap exceeded")
    accounting = dict(expected_jobs=len(jobs), paid_nanodollars=paid, unresolved_reserved_nanodollars=reserved,
                      maximum_liability_nanodollars=paid + reserved, cap_nanodollars=CAP, ledger_stop=settings[0][2])
    for source in ("whole", "edge"):
        counts = Counter(c["status"] for job, c in charges.items() if job.startswith(source + "/"))
        accounting[source] = {s: counts[s] for s in STATUSES}
    return charges, decisions, accounting


def paired_records(frames, edges, charges, decisions):
    paired, marks, omitted = [], [], []
    last = {}
    for f, e in zip(frames, edges, strict=True):
        name, second = f["frame"], f["second"]
        missing = {}
        for source, row in (("whole", f), ("edge", e)):
            if row["flags"]:
                status = charges[f"{source}/{name}"]["status"]
                if status != "usable":
                    missing[source] = status
        if missing:
            omitted.append(dict(frame=name, video=f["video"], second=second, jobs=missing))
            continue
        block = f["video"], f["block"]
        previous, start = last.get(block, (None, None))
        if previous != second - 1:
            start = second
        last[block] = second, start
        paired.append(dict(f, block=f"{f['block']}@{start}"))
        replacements = {i: decisions[f"edge/{name}", j] for j, i in enumerate(e["original_indices"])}
        for i in range(len(f["flags"])):
            original = decisions[f"whole/{name}", i]
            candidate = replacements.get(i, original)
            for arm, verdict in (("current", original), ("padded", candidate)):
                needs_cutoff = arm == "padded" and i in replacements
                if verdict["yes"] and (not needs_cutoff or verdict["confidence"] >= THRESHOLD):
                    marks.append(dict(arm=arm, frame=name, i=i, confidence=verdict["confidence"],
                                      delivery_second=second))
    return paired, marks, omitted


def measure(frames, truth, indexed, arm):
    scored = pilot.score_arm(frames, truth, indexed, arm)
    counts = {key: scored[key] for key in ("eligible_seconds", "identities", "found", "missed",
              "false_marks", "false_mark_seconds", "false_episodes", "ignored_marks")}
    people = scored["people"]
    counts.update(person_seconds=sum(len(p["marked_seconds"]) for p in people),
                  visible_person_seconds=sum(len(p["visible_seconds"]) for p in people),
                  true_marks=sum(len(p["hits"]) for p in people))
    counts["kept_marks"] = sum(len(indexed[arm, f["frame"]]) for f in frames)
    require(counts["kept_marks"] == counts["true_marks"] + counts["ignored_marks"] + counts["false_marks"],
            "Unreconciled marks")
    return counts, {p["track_id"]: p for p in people}


def compare(before, after):
    return dict(current=before, padded_edge=after, delta={k: after[k] - before[k] for k in before})


def score(frames, edges, truth, charges, decisions):
    paired, marks, omitted = paired_records(frames, edges, charges, decisions)
    indexed = pilot.index_marks(paired, marks)
    clips, ids = {}, []
    for video in sorted({f["video"] for f in frames}):
        subset = [f for f in paired if f["video"] == video]
        before, old = measure(subset, truth, indexed, "current")
        after, new = measure(subset, truth, indexed, "padded")
        clips[video] = compare(before, after)
        for track, person in old.items():
            candidate = new[track]
            ids.append(dict(video=video, track_id=track, visible_seconds=person["visible_seconds"],
                            current_found=bool(person["hits"]), padded_edge_found=bool(candidate["hits"]),
                            current_hit_seconds=person["marked_seconds"],
                            padded_edge_hit_seconds=candidate["marked_seconds"],
                            current_hits=person["hits"], padded_edge_hits=candidate["hits"]))
    totals = compare(sum_clip_counts(clips, "current"), sum_clip_counts(clips, "padded_edge"))
    changed = {}
    for label, old_hit, new_hit in (("gained_ids", False, True), ("lost_ids", True, False)):
        changed[label] = [dict(video=p["video"], track_id=p["track_id"]) for p in ids
                          if bool(p["current_hits"]) == old_hit and bool(p["padded_edge_hits"]) == new_hit]
    return dict(eligible_frames=len(frames), paired_frames=len(paired), omitted_frames=omitted,
                by_clip=clips, totals=totals, identities=ids, **changed,
                current_found_everyone_on_paired=(totals["current"]["missed"] == 0 if ids else None))


def sum_clip_counts(clips, arm):
    counts = Counter()
    for clip in clips.values():
        counts.update(clip[arm])
    return dict(counts)


def publish(folder, summary, charges, evidence, annotation_hash):
    with TemporaryDirectory(dir=folder) as tmp:
        stage = Path(tmp)
        for name, data in (("summary.json", summary), ("charges.json", list(charges.values()))):
            (stage / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
        hashes = {**evidence, **{n: digest(stage / n) for n in OUTPUTS[:2]}}
        (stage / "seal.json").write_text(json.dumps(dict(sha256=hashes, annotations_sha256=annotation_hash),
                                                  indent=2) + "\n")
        if (folder / "seal.json").exists():
            require(all((folder / n).is_file() and digest(folder / n) == digest(stage / n) for n in OUTPUTS),
                    "Existing result seal differs from replay")
        else:
            for name in OUTPUTS:
                (stage / name).replace(folder / name)


def run(folder, annotations, expected_lock):
    folder = folder.resolve()
    fd = os.open(folder, os.O_RDONLY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Run directory is busy") from None
        hashes = check_lock(folder, expected_lock)
        frames, edges, inputs = [read(folder / name) for name in ("fresh.json", "edges.json", "inputs.json")]
        jobs = expected_jobs(frames, edges, inputs)
        raw = annotations.read_bytes()
        annotation_hash = hashlib.sha256(raw).hexdigest()
        require(annotation_hash == ANNOTATIONS_SHA, "Wrong COCO annotations")
        # Only the clip guard changes. Keep the shared scorer and its global pilot cohort intact.
        load = pilot.load_truth
        scoped = FunctionType(load.__code__, dict(load.__globals__, VIDEOS={f["video"] for f in frames}))
        truth, audit = scoped(frames, json.loads(raw), read(folder / "exclusions.json"))
        charges, decisions, accounting = reconcile(folder, jobs, hashes["inputs.json"])
        results = score(frames, edges, truth, charges, decisions)
        summary = dict(model="muse-ember-1.0", route="personal Meta Model API", edge_threshold=THRESHOLD,
                       complete=not results["omitted_frames"] and accounting["ledger_stop"] is None,
                       cohort="Edge-enriched fresh windows. All 66 source videos had earlier still-image sampling.",
                       changed_ids_require_source_review=bool(results["gained_ids"] or results["lost_ids"]),
                       accounting=accounting, full_manifest_track_audit=audit, **results)
        evidence = {**hashes, "lock.json": expected_lock}
        paths = [folder / "ledger.sqlite", folder / "verdicts.jsonl", Path(__file__).resolve()]
        wal = folder / "ledger.sqlite-wal"
        if wal.exists() and wal.stat().st_size:
            paths.append(wal)
        for path in paths:
            evidence[os.path.relpath(path, folder)] = digest(path)
        check_lock(folder, expected_lock)
        publish(folder, summary, charges, evidence, annotation_hash)
        return summary
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=HERE)
    parser.add_argument("--annotations", type=Path,
                        default=pilot.ROOT / "../../data/mobdrone/annotations_person_coco_classes.json")
    parser.add_argument("--lock-sha256", required=True, help="Independently recorded pre-call lock.json SHA-256")
    args = parser.parse_args()
    try:
        summary = run(args.run_dir, args.annotations, args.lock_sha256)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        parser.exit(1, f"Cannot seal fresh results: {exc}\n")
    print(json.dumps({k: summary[k] for k in ("complete", "eligible_frames", "paired_frames", "totals",
                                              "gained_ids", "lost_ids")}))


if __name__ == "__main__":
    main()
