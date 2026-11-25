"""Write the replay data for pages/ from the sealed runs. Makes no model calls and reads no labels.

    python probe/build_pages.py

Each search's calls are kept in time order with their cost, duration and the points Ember returned,
read with the same rules as score.json. The pages load swimmer labels in the browser, and only after
probe/fetch_frames.py has downloaded them.

The landing page also gets the live two-minute run from runs/live-clip: every line the command printed with
its time, each second's final tile statuses, and the handoff message for each possible person, with the
labeled MOBDrone people that merge-rule-check.json found under it. It gets the same from runs/live-detector-check,
the one-command detector-then-Ember run on that clip, with each second's outcome: Ember kept a flag, dismissed every
flag, or the detector flagged nothing.
"""
import json
import re

from open_water_search import TILE_NAMES
from score import ROOT, TRAINING, VALIDATION, load_sealed, with_grid_rule

RUNS = {
    "validation": (VALIDATION, "Validation run · 30 untouched SeaDronesSee validation frames", "../validation/"),
    "probe": (TRAINING, "First run · 30 SeaDronesSee training frames", "../"),
}
LIVE_CLIP = ROOT / "runs/live-clip"
LIVE_CHECK = ROOT / "runs/live-detector-check"
# A printed line about one second of the flight: its overview, or a close look at a named tile.
FRAME_LINE = re.compile(r"second-(\d+): (?:overview|close look at the (.+?):)")


def call(record):
    evidence = record["evidence"]
    entry = dict(tile=record["tile"], paid=record["paid"], seconds=round(evidence["finished"] - evidence["started"], 2))
    if record["tile"] == -1:
        entry["ranking"] = evidence.get("tiles")
    else:
        entry["points"] = [[round(x, 1), round(y, 1), c] for x, y, c in evidence["points"]] if "points" in evidence else None
    return entry


def live_clip():
    record = json.loads((LIVE_CLIP / "search-record-redacted.json").read_text())
    printed = []
    # The sealed live clip's search record predates the decision log, so its printed lines come from terminal.jsonl
    # and each line's second and tile are read back from its text.
    for row in map(json.loads, (LIVE_CLIP / "terminal.jsonl").read_text().splitlines()):
        entry = dict(t=row["t"], line=row["line"])
        match = FRAME_LINE.match(row["line"])
        if match:
            entry["second"] = int(match[1])
            entry["tile"] = TILE_NAMES.index(match[2]) if match[2] else -1
        printed.append(entry)
    timeline = [[tile["status"] for tile in second["tiles"]] for second in record["coverage_timeline"]]
    return dict(printed=printed, timeline=timeline, people=possible_people(LIVE_CLIP))


def possible_people(run):
    """Each possible person in a sealed run, with the labeled MOBDrone people merge-rule-check.json found under it."""
    record = json.loads((run / "search-record-redacted.json").read_text())
    merge_check = json.loads((run / "merge-rule-check.json").read_text())
    held = {row["number"]: row["labeled_people"] for row in merge_check["by_possible_person"]}
    return [dict(number=person["number"], first=person["first_seen_second"], last=person["last_seen_second"],
                 message=person["handoff_message"], labeled_people=held[person["number"]])
            for person in record["possible_people"]]


def live_check():
    record = json.loads((LIVE_CHECK / "search-record-redacted.json").read_text())
    timeline = []
    for second in record["coverage_timeline"]:
        statuses = {flag["status"] for flag in second["flags"]}
        timeline.append("kept" if "kept" in statuses else "dismissed" if statuses else "none")
    printed = []
    for row in map(json.loads, (LIVE_CHECK / "terminal.jsonl").read_text().splitlines()):
        entry = dict(t=row["t"], line=row["line"])
        match = re.match(r"second-(\d+): ", row["line"])
        if match:
            entry["second"] = int(match[1])
        printed.append(entry)
    return dict(printed=printed, timeline=timeline, people=possible_people(LIVE_CHECK))


def main():
    out = ROOT / "pages/runs"
    out.mkdir(parents=True, exist_ok=True)
    for name, (base, title, prefix) in RUNS.items():
        trace, frames = load_sealed(base)
        trace = sorted(with_grid_rule(trace), key=lambda r: r["seq"])
        rows = []
        for f in frames:
            calls = {arm: [call(r) for r in trace if r["arm"] == arm and r["frame"] == f["frame"]] for arm in ("chosen", "grid")}
            rows.append(dict(frame=f["frame"], width=f["width"], height=f["height"],
                             image=prefix + "inputs/" + f["image"],
                             labels=prefix + "scoring-only/labels/" + f["frame"] + ".txt",
                             searches=calls))
        (out / f"{name}.json").write_text(json.dumps(dict(title=title, frames=rows)))
        print(name, len(rows), "frames", sum(len(c) for r in rows for c in r["searches"].values()), "calls")
    clip = live_clip()
    (out / "live-clip.json").write_text(json.dumps(clip))
    print("live-clip", len(clip["timeline"]), "seconds", len(clip["printed"]), "printed lines")
    check = live_check()
    (out / "live-detector-check.json").write_text(json.dumps(check))
    print("live-detector-check", len(check["timeline"]), "seconds", len(check["printed"]), "printed lines")


if __name__ == "__main__":
    main()
