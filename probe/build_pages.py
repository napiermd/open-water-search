"""Write the replay data for pages/ from the sealed runs. Makes no model calls and reads no labels.

    python probe/build_pages.py

Each search's calls are kept in time order with their cost, duration and the points Ember returned,
read with the same rules as score.json. The pages load swimmer labels in the browser, and only after
probe/fetch_frames.py has downloaded them.
"""
import json

from score import ROOT, load_sealed, with_grid_rule

RUNS = {
    "validation": (ROOT / "validation", "Validation run · 30 untouched SeaDronesSee validation frames", "../validation/"),
    "probe": (ROOT, "First run · 30 SeaDronesSee training frames", "../"),
}


def call(record):
    evidence = record["evidence"]
    entry = dict(tile=record["tile"], paid=record["paid"], seconds=round(evidence["finished"] - evidence["started"], 2))
    if record["tile"] == -1:
        entry["ranking"] = evidence.get("tiles")
    else:
        entry["points"] = [[round(x, 1), round(y, 1), c] for x, y, c in evidence["points"]] if "points" in evidence else None
    return entry


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


if __name__ == "__main__":
    main()
