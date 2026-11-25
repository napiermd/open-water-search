"""Seal an offline, stopped six-clip reserve run using its published pre-call lock."""
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
PILOT = HERE.parent / "harder-pilot"
sys.path.insert(0, str(PILOT))
import score_pilot as pilot

RESERVE_SHA = "bb5432ee3a7cab1d8fbf218158fbb9b65971fbe2facebd6084fee99f1bee2fbc"
PLAN_SHA = "08d9e34328c773a4478deb6566a052fa3ad98b9d8f45497eda52a00dbd1d8c68"
DOMINANT = "DJI_0915_0015_50m.mp4"
VIDEOS = {f"DJI_0915_{stem}.mp4" for stem in
          ("0015_50m", "0017_60m", "0019_60m", "0023_50m", "0027_50m", "0028_60m")}
CAP = 150_000_000
REQUIRED = {"PLAN.md", "reserve.json", "additions.json", "inputs.json", "exclusions.json",
            "audit.md", "tiled/seal.json", "tiled/boxes.json", "detector-input.json",
            "run_reserve.py", "../tile-flag-check/run.py", "../harder-pilot/run_pilot.py"}
COUNTS = ("eligible_seconds", "identities", "found", "visible_person_seconds", "person_seconds",
          "kept_marks", "true_marks", "ignored_marks", "false_marks", "false_mark_seconds",
          "false_episodes")
STATUSES = ("usable", "unusable", "unresolved", "unattempted")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def check_lock(folder, expected):
    path = folder / "lock.json"
    require(digest(path) == expected, "Published lock.json SHA-256 mismatch")
    hashes = read(path)
    require(REQUIRED <= hashes.keys(),
            "Incomplete pre-call lock (inputs, audit and runner code required)")
    for name, sha in hashes.items():
        require(digest(folder / name) == sha, f"Locked file changed: {name}")
    require(hashes["reserve.json"] == RESERVE_SHA and hashes["PLAN.md"] == PLAN_SHA,
            "Wrong reserve or plan")
    require((folder / "audit.md").read_text().strip(), "Empty pre-call land audit")
    tiled = read(folder / "tiled/seal.json")
    require(tiled["inputs_sha256"] == hashes["detector-input.json"] and
            tiled["boxes_sha256"] == hashes["tiled/boxes.json"], "Tiled detector seal mismatch")
    return hashes


def expected_jobs(frames, additions, inputs):
    """The two candidate lists define job identities independently of the runner manifest."""
    by_clip = defaultdict(list)
    expected = {}
    for f, more in zip(frames, additions, strict=True):
        name = f["frame"]
        require(more["frame"] == name and all(more.get(k) == v for k, v in f.items() if k != "flags"),
                f"Tile frame mismatch: {name}")
        pair = []
        for source, row in (("whole", f), ("tile", more)):
            job = f"{source}/{name}"
            require(job not in expected, f"Repeated source frame: {name}")
            expected[job] = dict(row, frame=job)
            pair.append(job)
        by_clip[f["video"]].append(pair)
    order = [job for turn in zip_longest(*by_clip.values()) for pair in turn if pair for job in pair]
    require(len(inputs) == len(order), "Wrong number of input jobs")
    for row, job in zip(inputs, order):
        require(row == expected[job], f"Wrong job identity, candidate list or round-robin order: {job}")
    return {job: row["flags"] for job, row in expected.items() if row["flags"]}


def verdict_key(row):
    return row["frame"], row["i"]


def check_verdict(row, job, flags):
    i = row["i"]
    require(row["frame"] == job and row["arm"] == "current" and
            type(i) is int and 0 <= i < len(flags), f"Invalid candidate reference: {job}, {i}")
    require(type(row["yes"]) is bool and type(row["confidence"]) in (float, int) and
            0 <= row["confidence"] <= 1 and row["nearby"] is False and isinstance(row["what"], str),
            f"Invalid current verdict: {job}, {i}")


def reconcile(folder, jobs, manifest):
    charges, decisions = {}, {}
    uri = (folder / "ledger.sqlite").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("BEGIN")
        settings = db.execute("SELECT id, manifest, stop FROM settings").fetchall()
        require(len(settings) == 1 and settings[0][:2] == (1, manifest), "Ledger manifest mismatch")
        stop = settings[0][2]
        for arm, job, i, reserved, paid, result in db.execute(
                "SELECT arm, frame, i, reserved, paid, result FROM calls ORDER BY frame"):
            require(arm == "current" and i == -1 and job in jobs and job not in charges,
                    f"Unexpected ledger job: {(arm, job, i)}")
            require(type(reserved) is int and 0 < reserved <= CAP and
                    (paid is None or type(paid) is int and 0 <= paid <= reserved),
                    f"Invalid reservation or charge: {job}")
            if result is None:
                status = "unresolved" if paid is None else "unusable"
            else:
                require(paid is not None, f"Unsettled job has decisions: {job}")
                rows = json.loads(result)
                require(isinstance(rows, list) and len(rows) == len(jobs[job]),
                        f"Incomplete decision batch: {job}")
                for row in rows:
                    check_verdict(row, job, jobs[job])
                    key = verdict_key(row)
                    require(key not in decisions, f"Repeated decision: {key}")
                    decisions[key] = row
                status = "usable"
            charges[job] = dict(arm=arm, frame=job, i=i, reserved_nanodollars=reserved,
                                paid_nanodollars=paid, status=status)
    for job in sorted(jobs.keys() - charges.keys()):
        charges[job] = dict(arm="current", frame=job, i=-1, reserved_nanodollars=0,
                            paid_nanodollars=None, status="unattempted")
    logged = {}
    for line in (folder / "verdicts.jsonl").read_text().splitlines():
        row = json.loads(line)
        job = row["frame"]
        require(job in jobs, f"Unexpected exported job: {job}")
        check_verdict(row, job, jobs[job])
        key = verdict_key(row)
        require(key not in logged, f"Repeated exported decision: {key}")
        logged[key] = row
    require(logged == decisions, "Exported verdicts disagree with ledger")
    paid = sum(c["paid_nanodollars"] or 0 for c in charges.values())
    outstanding = sum(c["reserved_nanodollars"] for c in charges.values() if c["status"] == "unresolved")
    require(paid + outstanding <= CAP, "Shared spending cap exceeded")
    accounting = dict(expected_jobs=len(jobs), ledger_stop=stop,
                      paid_nanodollars=paid, unresolved_reserved_nanodollars=outstanding,
                      maximum_liability_nanodollars=paid + outstanding, cap_nanodollars=CAP)
    for source in ("whole", "tile"):
        counts = Counter(c["status"] for k, c in charges.items() if k.startswith(source + "/"))
        accounting[source] = {s: counts[s] for s in STATUSES}
    return charges, decisions, accounting


def load_reserve_truth(frames, annotations, exclusions):
    # Keep the sealed COCO join byte-for-byte. Bind only its cohort guard in a
    # private globals dictionary, preserving the real clip names and original guard.
    require({f["video"] for f in frames} <= VIDEOS, "Outside reserve")
    load = pilot.load_truth
    reserve_load = FunctionType(load.__code__, dict(load.__globals__, VIDEOS=VIDEOS), load.__name__)
    return reserve_load(frames, annotations, exclusions)


def paired_marks(frames, additions, charges, decisions):
    stacked, baseline, combined, omitted = [], [], [], []
    last = {}
    for f, more in zip(frames, additions, strict=True):
        name, second = f["frame"], f["second"]
        missing = {source: charges[f"{source}/{name}"]["status"]
                   for source, flags in (("whole", f["flags"]), ("tile", more["flags"]))
                   if flags and charges[f"{source}/{name}"]["status"] != "usable"}
        if missing:
            omitted.append(dict(frame=name, jobs=missing))
            continue
        block = f["video"], f["block"]
        previous, start = last.get(block, (None, None))
        if previous != second - 1:
            start = second
        last[block] = second, start
        stacked.append(dict(f, flags=f["flags"] + more["flags"], block=f"{f['block']}@{start}"))
        for source, flags in (("whole", f["flags"]), ("tile", more["flags"])):
            for i in range(len(flags)):
                v = decisions[f"{source}/{name}", i]
                if not v["yes"] or (source == "tile" and v["confidence"] < .92):
                    continue
                mark = dict(arm="current", frame=name, i=i if source == "whole" else len(f["flags"]) + i,
                            delivery_second=second, confidence=v["confidence"])
                combined.append(mark)
                if source == "whole":
                    baseline.append(mark)
    return stacked, baseline, combined, omitted


def measure(frames, truth, marks):
    scored = pilot.score_arm(frames, truth, pilot.index_marks(frames, marks), "current")
    people = scored["people"]
    hits = sum(len(p["hits"]) for p in people)
    metrics = dict(scored, true_marks=hits, kept_marks=len(marks),
                   person_seconds=sum(len(p["marked_seconds"]) for p in people),
                   visible_person_seconds=sum(len(p["visible_seconds"]) for p in people))
    require(hits + scored["false_marks"] + scored["ignored_marks"] == len(marks), "Mark count mismatch")
    return {k: metrics[k] for k in COUNTS}, pilot.found(scored)


def comparison(base, combined):
    return dict(baseline=base, combined=combined, delta={k: combined[k] - base[k] for k in COUNTS})


def score(frames, additions, truth, charges, decisions):
    paired, base, combined, omitted = paired_marks(frames, additions, charges, decisions)
    originals = {f["frame"]: f for f in frames}
    tiles = {f["frame"]: f for f in additions}
    by_clip, added_ids = {}, []
    for video in sorted({f["video"] for f in frames}):
        subset = [f for f in paired if f["video"] == video]
        names = {f["frame"] for f in subset}
        before, old_people = measure(subset, truth, [m for m in base if m["frame"] in names])
        after, new_people = measure(subset, truth, [m for m in combined if m["frame"] in names])
        require(old_people.keys() <= new_people.keys(), "Combined record lost a baseline ID")
        by_clip[video] = comparison(before, after)
        for key in sorted(new_people.keys() - old_people.keys()):
            p = new_people[key]
            marks = []
            for hit in p["hits"]:
                f = originals[hit["frame"]]
                i = hit["i"] - len(f["flags"])
                v = decisions[f"tile/{f['frame']}", i]
                box = next(box for track, box, ignored in truth[f["frame"]] if track == key[1] and not ignored)
                more = tiles[f["frame"]]
                marks.append(dict(frame=f["frame"], second=f["second"], video_frame=f["video_frame"],
                                  image=f["image"], job_frame=v["frame"], i=i, point=hit["point"],
                                  candidate_box=more["flags"][i][:4], tile_rank_index=more["tile_indices"][i],
                                  label_box=box, confidence=v["confidence"], what=v["what"]))
            added_ids.append(dict(video=video, track_id=key[1], verification_status="pending_source_review",
                                  frames=list(dict.fromkeys(m["frame"] for m in marks)), marks=marks))
    totals = {}
    for group, clips in (("all", by_clip), ("excluding_dominant", set(by_clip) - {DOMINANT})):
        counts = [{k: sum(by_clip[v][arm][k] for v in clips) for k in COUNTS}
                  for arm in ("baseline", "combined")]
        totals[group] = comparison(*counts)
    return dict(eligible_frames=len(frames), paired_frames=len(paired), omitted_frames=omitted,
                dominant_flight=DOMINANT, totals=totals, by_clip=by_clip, added_ids=added_ids)


def publish(folder, charges, summary, hashes, annotation_hash):
    # Stage both payloads and commit the seal last. Replaying an existing seal
    # checks identical bytes, including its inputs, before returning success.
    with TemporaryDirectory(dir=folder) as tmp:
        stage = Path(tmp)
        def write(name, value):
            (stage / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        write("charges.json", [charges[k] for k in sorted(charges)])
        write("summary.json", summary)
        seal = dict(sha256={**hashes, **{n: digest(stage / n) for n in ("charges.json", "summary.json")}},
                    annotations_sha256=annotation_hash)
        write("seal.json", seal)
        names = ("charges.json", "summary.json", "seal.json")
        if (folder / "seal.json").exists():
            require(all((folder / n).is_file() and digest(folder / n) == digest(stage / n) for n in names),
                    "Existing result seal differs from replay")
        else:
            for name in names:
                (stage / name).replace(folder / name)


def run(folder, annotations, expected_lock):
    fd = os.open(folder, os.O_RDONLY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Run directory is busy. Score after the runner exits.") from None
        hashes = check_lock(folder, expected_lock)
        frames, additions, inputs = [read(folder / n) for n in ("reserve.json", "additions.json", "inputs.json")]
        jobs = expected_jobs(frames, additions, inputs)
        charges, decisions, accounting = reconcile(folder, jobs, hashes["inputs.json"])
        pilot_seal = read(PILOT / "seal.json")
        require(digest(PILOT / "score_pilot.py") == pilot_seal["sha256"]["score_pilot.py"],
                "Harder-pilot scorer changed")
        raw = annotations.read_bytes()
        annotation_hash = hashlib.sha256(raw).hexdigest()
        require(annotation_hash == pilot_seal["annotations_sha256"], "Wrong COCO annotations")
        truth, audit = load_reserve_truth(frames, json.loads(raw), read(folder / "exclusions.json"))
        results = score(frames, additions, truth, charges, decisions)
        summary = dict(model="muse-ember-1.0", route="personal Meta Model API", tile_threshold=.92,
                       complete=not results["omitted_frames"] and accounting["ledger_stop"] is None,
                       accounting=accounting, track_audit=audit, **results)
        evidence = dict(hashes)
        for path in (folder / "ledger.sqlite", folder / "verdicts.jsonl", Path(__file__).resolve(),
                     PILOT / "score_pilot.py", PILOT / "seal.json", pilot.ROOT / "probe/score.py"):
            evidence[os.path.relpath(path, folder)] = digest(path)
        wal = folder / "ledger.sqlite-wal"
        if wal.exists() and wal.stat().st_size:
            evidence[wal.name] = digest(wal)
        evidence["lock.json"] = expected_lock
        check_lock(folder, expected_lock)
        publish(folder, charges, summary, evidence, annotation_hash)
        return summary
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=HERE)
    parser.add_argument("--annotations", type=Path, default=pilot.ROOT / "../../data/mobdrone/annotations_person_coco_classes.json")
    parser.add_argument("--lock-sha256", required=True, help="SHA-256 of lock.json published before calls")
    args = parser.parse_args()
    try:
        summary = run(args.run_dir.resolve(), args.annotations, args.lock_sha256)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        parser.exit(1, f"Cannot seal reserve results: {exc}\n")
    print(json.dumps({k: summary[k] for k in ("complete", "eligible_frames", "paired_frames", "totals")}))


if __name__ == "__main__":
    main()
