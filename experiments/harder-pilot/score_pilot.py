"""Offline scorer for the preregistered seven-clip MOBDrone pilot (PLAN.md).

Run from the repo root with --marks MARKS.json --exclusions EXCLUSIONS.json.
JSON is written to stdout. Pass --complete only for a sealed, complete run.
Scoring never opens images. Review gained identities separately using their
frame/flag references before making a claim about a newly found person.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "probe"))
from score import contains, score_photo

ARMS = ("detector", "current", "padded", "vote", "three", "two_way")
VIDEOS = {f"DJI_{stem}.mp4" for stem in (
    "0804_0009_40m", "0804_0010_60m", "0804_0012_50m_3", "0804_0017_40m",
    "0804_0018_40m", "0915_0003_50m", "0915_0018_60m")}
PILOT_SHA256 = "6b584a523df6c298a38bb8fa147aaeedffcc58d974eb3e8cd51d4239c305fe22"


def center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def load_truth(frames, coco, exclusions):
    """Join selected COCO images by exact source filename, then project only their person rows."""
    names = {}
    for f in frames:
        if f["video"] not in VIDEOS:
            raise ValueError(f"Outside pilot: {f['video']}")
        names[f"{Path(f['video']).stem}_{f['video_frame']:06}.PNG"] = f
    images = {}
    for image in coco["images"]:
        f = names.get(image["file_name"])
        if f is not None:
            if (image["width"], image["height"]) != (f["width"], f["height"]):
                raise ValueError(f"Image dimensions differ: {f['frame']}")
            images[image["id"]] = f
    if len(images) != len(frames) or len({f['frame'] for f in images.values()}) != len(frames):
        raise ValueError("Missing or duplicate pilot image in annotations")

    land = {(e["video"], e["second"], e["track_id"]) for e in exclusions}
    if len(land) != len(exclusions) or any(type(k[2]) is not int for k in land):
        raise ValueError("Invalid or duplicate land exclusion")
    used_land = set()
    truth = {f["frame"]: [] for f in frames}
    seen = set()
    missing = 0
    tracks = defaultdict(set)
    for ann in coco["annotations"]:
        f = images.get(ann["image_id"])
        if f is None or ann["category_id"] != 1:
            continue
        track = ann.get("attributes", {}).get("track_id")
        key = (f["video"], f["second"], track)
        if track is None:
            missing += 1
        else:
            if type(track) is not int or track < 0 or key in seen:
                raise ValueError(f"Invalid or duplicate track ID: {key}")
            seen.add(key)
            tracks[track].add(f["video"])
        ignored = track is None or key in land
        if key in land:
            used_land.add(key)
        x, y, w, h = ann["bbox"]
        if not all(math.isfinite(v) for v in (x, y, w, h)) or min(w, h) <= 0:
            raise ValueError(f"Invalid person box: {key}")
        truth[f["frame"]].append((track, (x, y, x + w, y + h), ignored))
    if land != used_land:
        raise ValueError(f"Unmatched land exclusions: {sorted(land - used_land)}")
    audit = dict(selected_images=len(images), person_boxes=sum(map(len, truth.values())),
                 missing_track_boxes=missing, land_boxes=len(land),
                 clip_track_ids=sum(map(len, tracks.values())),
                 ids_reused_across_clips={k: sorted(v) for k, v in tracks.items() if len(v) > 1})
    # A large one-second jump is a review cue, not proof of an identity switch.
    jumps = []
    last = {}
    for f in sorted(frames, key=lambda row: (row["video"], row["second"])):
        for track, box, _ in truth[f["frame"]]:
            if track is None:
                continue
            key = f["video"], track
            prior = last.get(key)
            if prior and prior[0] == f["second"] - 1:
                fraction = math.dist(prior[1], center(box)) / f["width"]
                if fraction > .1:
                    jumps.append(dict(video=f["video"], track_id=track, from_second=prior[0],
                                      to_second=f["second"], displacement_in_frame_widths=fraction))
            last[key] = f["second"], center(box)
    audit["one_second_track_jumps_over_tenth_width"] = jumps
    return truth, audit


def index_marks(frames, marks):
    lookup = {f["frame"]: f for f in frames}
    indexed = defaultdict(list)
    seen = set()
    for mark in marks:
        arm, frame, i = mark["arm"], mark["frame"], mark["i"]
        key = (arm, frame, i)
        if arm not in ARMS or frame not in lookup or type(i) is not int:
            raise ValueError(f"Unknown mark reference: {key}")
        f = lookup[frame]
        if not 0 <= i < len(f["flags"]) or key in seen:
            raise ValueError(f"Invalid or duplicate flag reference: {key}")
        seen.add(key)
        delivery = mark["delivery_second"]
        confidence = mark.get("confidence", f["flags"][i][4])
        if not math.isfinite(delivery) or delivery < f["second"]:
            raise ValueError(f"Invalid delivery time: {key}")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"Invalid confidence: {key}")
        indexed[arm, frame].append(dict(mark, confidence=confidence))
    for rows in indexed.values():
        rows.sort(key=lambda row: row["i"])
    return indexed


def full_window(frames):
    seconds = {(f["video"], f["block"], f["second"]) for f in frames}
    return [f for f in frames if all((f["video"], f["block"], s) in seconds
                                     for s in range(f["second"] - 3, f["second"] + 4))]


def false_burden(frames, false):
    """Link unmatched observations within their own block, in detector rank order."""
    episodes = []
    for f in frames:
        s = f["second"]
        available = [ep for ep in episodes if 0 < s - ep[-1]["second"] <= 2]
        for m in sorted(false[f["frame"]], key=lambda m: (-f["flags"][m["i"]][4], m["i"])):
            near = [ep for ep in available
                    if math.dist(ep[-1]["point"], m["point"]) <= .1 * f["width"]]
            if near:
                ep = min(near, key=lambda ep: math.dist(ep[-1]["point"], m["point"]))
                available.remove(ep)
            else:
                ep = []
                episodes.append(ep)
            ep.append(m)
    return dict(eligible_seconds=len(frames), false_marks=sum(map(len, episodes)),
                false_mark_seconds=sum(bool(false[f["frame"]]) for f in frames),
                false_episodes=len(episodes))


def with_rates(counts):
    n = counts["eligible_seconds"]
    return {**counts, **{f"{k}_per_minute": 60 * counts[k] / n if n else None
                         for k in ("false_marks", "false_mark_seconds", "false_episodes")}}


def identity_metrics(people):
    delays = [p["first_alert_delay"] for p in people if p["first_alert_delay"] is not None]
    return dict(identities=len(people), found=len(delays), missed=len(people) - len(delays),
                mean_coverage=mean(p["coverage"] for p in people) if people else None,
                median_first_alert_delay=median(delays) if delays else None,
                max_first_alert_delay=max(delays, default=None))


def score_arm(frames, truth, indexed, arm):
    people = {}
    blocks = defaultdict(list)
    false = defaultdict(list)
    legacy = Counter(dict(appearances=0, found=0, missed=0, unmatched=0))
    ignored_marks = 0
    for f in sorted(frames, key=lambda f: (f["video"], f["second"])):
        frame, video, s = f["frame"], f["video"], f["second"]
        blocks[video, f["block"]].append(f)
        labels = truth[frame]
        for track, _, ignored in labels:
            if not ignored:
                p = people.setdefault((video, track), dict(video=video, track_id=track,
                                      visible_seconds=[], hits=[]))
                p["visible_seconds"].append(s)
        points = []
        for mark in indexed.get((arm, frame), []):
            i = mark["i"]
            point = center(f["flags"][i])
            points.append([*point, mark["confidence"]])
            boxes = [row for row in labels if contains(point, row[1])]
            hit = dict(frame=frame, second=s, i=i, delivery_second=mark["delivery_second"],
                       point=point)
            if not boxes:
                false[frame].append(hit)
                continue
            # Stable COCO order breaks exact distance ties, as in check_merge_rule.holder.
            track, _, ignored = min(boxes, key=lambda row: math.dist(point, center(row[1])))
            if ignored:
                ignored_marks += 1
            else:
                people[video, track]["hits"].append(hit)

        # Historical appearance score uses every person box, including untracked/land.
        old = score_photo(points, [(0, box) for _, box, _ in labels])
        legacy.update(dict(appearances=len(labels), found=old["found"], missed=old["missed"],
                           unmatched=sum(old["unmatched"].values())))

    for p in people.values():
        hits = p["hits"]
        p["marked_seconds"] = sorted({h["second"] for h in hits})
        p["coverage"] = len(p["marked_seconds"]) / len(p["visible_seconds"])
        first = min((h["delivery_second"] for h in hits), default=None)
        p["first_delivery_second"] = first
        p["first_alert_delay"] = first - p["visible_seconds"][0] if first is not None else None

    by_clip = {}
    total = Counter(dict(eligible_seconds=0, false_marks=0, false_mark_seconds=0, false_episodes=0))
    for video in sorted({f["video"] for f in frames}):
        per_block = {b: false_burden(rows, false) for (v, b), rows in blocks.items() if v == video}
        counts = Counter()
        for values in per_block.values():
            counts.update(values)
        total.update(counts)
        rows = [p for (v, _), p in people.items() if v == video]
        by_clip[video] = dict(**identity_metrics(rows), **with_rates(counts),
                              blocks={b: with_rates(vals) for b, vals in per_block.items()})
    return dict(**identity_metrics(list(people.values())), **with_rates(total), by_clip=by_clip,
                people=[people[k] for k in sorted(people)], ignored_marks=ignored_marks,
                legacy_five=dict(legacy))


def found(arm):
    return {(p["video"], p["track_id"]): p for p in arm["people"] if p["hits"]}


def identity_changes(candidate, control):
    return dict(gained=[candidate[k] for k in sorted(candidate.keys() - control.keys())],
                lost=[control[k] for k in sorted(control.keys() - candidate.keys())])


def compare(arms):
    hits = {name: found(report) for name, report in arms.items()}
    union = {**hits["current"], **hits["padded"]}
    comparisons = {}
    for name in ("vote", "three", "two_way"):
        per_control = {control: identity_changes(hits[name], hits[control])
                       for control in ("current", "padded", "detector")}
        per_control["single_frame_union"] = identity_changes(hits[name], union)
        comparisons[name] = per_control
    return comparisons


def decision(arms, changes, complete):
    results = {}
    for name in ("vote", "three"):
        row, padded = arms[name], arms["padded"]
        increases = {}
        for video, clip in row["by_clip"].items():
            baseline = padded["by_clip"][video]
            worse = {k: clip[k] - baseline[k] for k in ("false_mark_seconds", "false_episodes")
                     if clip[k] > baseline[k]}
            if worse:
                increases[video] = worse
        delta = None if row["mean_coverage"] is None else row["mean_coverage"] - padded["mean_coverage"]
        above_best = row["found"] - max(padded["found"], arms["current"]["found"])
        diff = changes[name]["single_frame_union"]
        endpoint = (delta is not None and delta >= .05 - 1e-12) if name == "vote" else above_best >= 1
        gates = dict(complete=complete, endpoint=endpoint, retained_control_union=not diff["lost"],
                     no_clip_false_increase=not increases)
        results[name] = dict(passes=all(gates.values()), gates=gates, coverage_delta=delta,
                             count_above_best_single=above_best, genuinely_new_ids=len(diff["gained"]),
                             false_increases=increases)
    winner = next((a for a in ("three", "vote") if results[a]["passes"]), "current")
    return dict(arms=results, numerical_selection=winner if complete else None,
                new_id_crop_review_required=bool(changes["three"]["single_frame_union"]["gained"]))


def score(frames, truth, marks, complete=False):
    indexed = index_marks(frames, marks)
    if complete and any(len(indexed["detector", f["frame"]]) != len(f["flags"]) for f in frames):
        raise ValueError("Complete run is missing detector marks")
    result = {}
    for name, subset in (("all", frames), ("full_window", full_window(frames))):
        arms = {arm: score_arm(subset, truth, indexed, arm) for arm in ARMS}
        changes = compare(arms)
        result[name] = dict(seconds=len(subset), arms=arms, comparisons=changes)
        if name == "all":
            result["decision"] = decision(arms, changes, complete)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=HERE / "pilot.json")
    parser.add_argument("--annotations", type=Path, default=ROOT / "../../data/mobdrone/annotations_person_coco_classes.json")
    parser.add_argument("--marks", type=Path, required=True)
    parser.add_argument("--exclusions", type=Path, required=True)
    parser.add_argument("--complete", action="store_true", help="attest all six arms finished")
    args = parser.parse_args()
    raw = args.pilot.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PILOT_SHA256:
        parser.error("pilot.json does not match the preregistered seven-clip manifest")
    frames = json.loads(raw)
    truth, audit = load_truth(frames, json.loads(args.annotations.read_bytes()),
                              json.loads(args.exclusions.read_bytes()))
    report = score(frames, truth, json.loads(args.marks.read_bytes()), args.complete)
    print(json.dumps(dict(track_audit=audit, **report), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
