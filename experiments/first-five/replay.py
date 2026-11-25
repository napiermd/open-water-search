"""Score the pinned, first-seen handoffs. All inputs are local recorded artifacts."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "probe"))
from check_merge_rule import holder, labeled_people
from open_water_search import possible_people, tile_containing


def read(path, digest=None):
    raw = path.read_bytes()
    if digest and sha256(raw).hexdigest() != digest:
        raise ValueError(f"Receipt mismatch for {path}")
    return json.loads(raw)


def make_queue(timeline, mode):
    sightings = []
    for row in timeline:
        for flag in row["flags"]:
            if mode == "detector" and flag["detector_confidence"] < 0.30:
                continue
            if mode == "ember" and not flag.get("kept", flag.get("status") == "kept"):
                continue
            x1, y1, x2, y2 = flag["box"]
            x, y = (x1+x2)/2, (y1+y2)/2
            confidence = flag["detector_confidence"] if mode == "detector" else flag.get("confidence", flag.get("ember_confidence"))
            sightings.append(dict(frame=row["frame"], second=row["second"], x=x, y=y,
                                  confidence=confidence, what=flag.get("description", flag.get("what", "")),
                                  tile=tile_containing(row["width"], row["height"], x, y)))
    # The formatter expects status fields. Grouping uses only names, widths, seconds and sightings.
    frames = [dict(frame=r["frame"], width=r["width"], flags=[]) for r in timeline]
    return possible_people(sightings, frames)


def summarize(queue, labels):
    seen = set()
    tally = dict(new=0, repeat=0, empty=0, unidentified=0)
    outcomes = []
    for person in queue[:5]:
        pin = person["position"]
        match = holder(pin, labels[pin["frame"]])
        if match is None:
            outcome = "empty"
        elif match[0] is None:
            outcome = "unidentified"
        elif match[0] in seen:
            outcome = "repeat"
        else:
            outcome = "new"
            seen.add(match[0])
        tally[outcome] += 1
        outcomes.append(outcome)
    return dict(**tally, available=len(queue), opened=len(outcomes), outcomes=outcomes)


def clip_labels(rows, coco):
    names = {f"{Path(r['video']).stem}_{r['video_frame']:06}.PNG": r for r in rows}
    ids = {}
    for image in coco["images"]:
        row = names.get(image["file_name"])
        if row:
            if (row["width"], row["height"]) != (image["width"], image["height"]):
                raise ValueError("Label and frame dimensions differ")
            ids[image["id"]] = row["frame"]
    if len(set(ids.values())) != len(rows) or len(ids) != len(rows):
        raise ValueError("Incomplete or ambiguous annotations")
    labels = {r["frame"]: [] for r in rows}
    for ann in coco["annotations"]:
        if ann["category_id"] == 1 and ann["image_id"] in ids:
            x, y, w, h = ann["bbox"]
            labels[ids[ann["image_id"]]].append((ann.get("attributes", {}).get("track_id"), [x,y,x+w,y+h]))
    return labels


def count_people(labels):
    return len({track for people in labels.values() for track, box in people if track is not None})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locked", type=Path)
    parser.add_argument("windows", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("flight_labels", type=Path)
    args = parser.parse_args()
    receipt = read(args.locked / "receipt.json")
    windows = read(args.windows, receipt["input_hashes"]["windows.json"])
    coco = read(args.annotations)
    clips = []
    for n, window in enumerate(windows, 1):
        if window["role"] != "primary":
            continue
        clip = {}
        for mode in ("detector", "ember"):
            key = f"queues/window-{n:02}/{mode}.json"
            rows = read(args.locked / key, receipt["queue_hashes"][key])
            if len(rows) != 24 or any(r["video"] != window["video"] or r["second"] != window["start"]+i for i,r in enumerate(rows)):
                raise ValueError("Window does not match its lock")
            labels = clip_labels(rows, coco)
            clip["labeled"] = count_people(labels)
            clip[mode] = summarize(make_queue(rows, mode), labels)
        clips.append(clip)
    if len(clips) != 8 or sum(c["labeled"] for c in clips) != 7:
        raise ValueError("Primary population mismatch")
    totals = {}
    for mode in ("detector","ember"):
        totals[mode] = {k:sum(c[mode][k] for c in clips) for k in ("opened","new","repeat","empty","unidentified")}
    record = read(ROOT / "runs/live-detector-check/search-record-redacted.json")
    timeline = record["coverage_timeline"]
    labels = labeled_people(args.flight_labels, timeline)
    flight = {"labeled":count_people(labels)}
    for mode in ("detector","ember"):
        queue = make_queue(timeline,mode)
        if mode == "ember" and [p["position"] for p in queue] != [p["position"] for p in record["possible_people"]]:
            raise ValueError("Failed to reproduce the shipped handoffs")
        flight[mode] = summarize(queue, labels)
    print(json.dumps(dict(primary=clips, totals=totals, flight=flight), indent=2))


if __name__ == "__main__":
    main()
