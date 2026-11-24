"""Write the replay data for pages/ from the sealed runs. Makes no model calls and reads no labels.

    python probe/build_pages.py

Each search's calls are kept in time order with their cost, duration and the points Ember returned,
read with the same rules as score.json. The pages load swimmer labels in the browser, and only after
probe/fetch_frames.py has downloaded them.

The landing page also gets the live two-minute run from runs/live-clip: every line the command printed with
its time, each second's final tile statuses, and the handoff message for each possible person, with the
labeled MOBDrone people that merge-rule-check.json found under it.
"""
import json
import re

from open_water_search import TILE_NAMES
from score import ROOT, load_sealed, with_grid_rule

RUNS = {
    "validation": (ROOT / "validation", "Validation run · 30 untouched SeaDronesSee validation frames", "../validation/"),
    "probe": (ROOT, "First run · 30 SeaDronesSee training frames", "../"),
}
LIVE_CLIP = ROOT / "runs/live-clip"
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
    for row in map(json.loads, (LIVE_CLIP / "terminal.jsonl").read_text().splitlines()):
        entry = dict(t=row["t"], line=row["line"])
        match = FRAME_LINE.match(row["line"])
        if match:
            entry["second"] = int(match[1])
            entry["tile"] = TILE_NAMES.index(match[2]) if match[2] else -1
        printed.append(entry)
    timeline = [[tile["status"] for tile in second["tiles"]] for second in record["coverage_timeline"]]
    merge_check = json.loads((LIVE_CLIP / "merge-rule-check.json").read_text())
    held = {row["number"]: row["labeled_people"] for row in merge_check["by_possible_person"]}
    people = [dict(number=person["number"], first=person["first_seen_second"], last=person["last_seen_second"],
                   message=person["handoff_message"], labeled_people=held[person["number"]])
              for person in record["possible_people"]]
    return dict(printed=printed, timeline=timeline, people=people)


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


if __name__ == "__main__":
    main()
