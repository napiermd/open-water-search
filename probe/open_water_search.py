"""Search a folder of drone frames for swimmers with Muse Ember.

    MODEL_API_KEY=... python open_water_search.py FRAMES_DIR --out RESULTS_DIR --budget 0.05

Every frame first gets one overview, in which Ember ranks the nine tiles of a 3 x 3 grid. Then each frame
gets close looks at its top-ranked tiles, one round at a time, until the per-frame look count or the budget
runs out. The worst-case cost of every request is checked against the budget before it is sent.

RESULTS_DIR receives:
  report.html    the reviewer queue and a coverage map of every frame
  queue.json     ranked sightings, up to five per frame
  coverage.json  per frame, the tiles Ember checked, flagged, could not read, or never reached
  calls.jsonl    every Ember request with its token usage and cost

The prompts, image preparation, output limit and answer readers are the ones used in the November 23
30-frame run and its validation repeat.
"""
import argparse
import base64
import html
import json
import os
import time
from pathlib import Path

from PIL import Image

from runner import INSPECT, LIMIT, MODEL, NANO, OVERVIEW, Meta, interpret, prepare, price, rectangle
from score import grid_points

TILE_NAMES = ["top left", "top center", "top right", "middle left", "center",
              "middle right", "bottom left", "bottom center", "bottom right"]
REVIEW_LIMIT = 5
FAILURE_LIMIT = 10


class OutOfBudget(Exception):
    pass


def dollars(nanodollars):
    return "$" + format(nanodollars / NANO, ".4f")


class Search:
    def __init__(self, api, budget_nano, out):
        self.api = api
        self.budget = budget_nano
        self.spent = 0
        self.out = out
        self.calls = (out / "calls.jsonl").open("a")
        self.failures_in_a_row = 0

    def ask(self, frame, tile):
        """Send one overview (tile -1) or close look, and return the read answer."""
        rect = rectangle(frame["width"], frame["height"], tile)
        image = prepare(frame["path"], rect)
        prompt = OVERVIEW if tile == -1 else INSPECT
        body = {"model": MODEL, "reasoning": {"effort": "minimal"}, "max_output_tokens": LIMIT,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}]}]}
        worst = price(self.api.count(body), 0, LIMIT)
        if self.spent + worst > self.budget:
            raise OutOfBudget()
        started = time.time()
        reply = self.api.generate(body)
        finished = time.time()
        usage = reply["usage"]
        paid = price(usage["input_tokens"], usage["input_tokens_details"]["cached_tokens"], usage["output_tokens"])
        self.spent += paid
        event = interpret(dict(rect=rect, response=reply, started=started, finished=finished), tile)
        converted = grid_points(dict(tile=tile, evidence=event))
        if converted is not None:
            event.pop("failure")
            event["points"] = converted
        self.calls.write(json.dumps(dict(frame=frame["name"], tile=tile, paid_nanodollars=paid, usage=usage,
                                         seconds=round(finished - started, 3), answer=event)) + "\n")
        self.calls.flush()
        self.failures_in_a_row = self.failures_in_a_row + 1 if "failure" in event else 0
        if self.failures_in_a_row >= FAILURE_LIMIT:
            raise RuntimeError(f"{FAILURE_LIMIT} unreadable answers in a row")
        if tile >= 0:
            (self.out / "crops" / f"{frame['name']}-t{tile}.jpg").write_bytes(image)
        return event


def load_frames(folder):
    frames = []
    for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")):
        with Image.open(path) as image:
            width, height = image.size
        frames.append(dict(path=path, name=path.stem, width=width, height=height,
                           overview="awaiting overview", ranking=[], tiles={}))
    if not frames:
        raise SystemExit(f"No .jpg, .jpeg or .png frames in {folder}")
    return frames


def run(search, frames, looks):
    """Overview every frame, then give each frame its next ranked close look, one round at a time."""
    for frame in frames:
        event = search.ask(frame, -1)
        frame["ranking"] = event.get("tiles", [])
        frame["overview"] = "done" if frame["ranking"] else "unreadable"
    for round_number in range(looks):
        for frame in frames:
            if round_number < len(frame["ranking"]):
                tile = frame["ranking"][round_number]
                frame["tiles"][tile] = search.ask(frame, tile).get("points")


def summarize(frames):
    queue, coverage = [], []
    for frame in frames:
        sightings, tiles = [], []
        for tile in range(9):
            if tile not in frame["tiles"]:
                status = "not checked"
            elif frame["tiles"][tile] is None:
                status = "unreadable"
            else:
                points = frame["tiles"][tile]
                status = "flagged" if points else "checked, no sighting"
                left, top, right, bottom = rectangle(frame["width"], frame["height"], tile)
                sightings += [dict(frame=frame["name"], tile=tile, tile_name=TILE_NAMES[tile], x=round(x, 1), y=round(y, 1),
                                   confidence=c, crop=f"crops/{frame['name']}-t{tile}.jpg",
                                   crop_x=(x - left) / (right - left), crop_y=(y - top) / (bottom - top))
                              for x, y, c in points]
            tiles.append(dict(tile=tile, name=TILE_NAMES[tile], status=status))
        queue += sorted(sightings, key=lambda s: -s["confidence"])[:REVIEW_LIMIT]
        coverage.append(dict(frame=frame["name"], width=frame["width"], height=frame["height"],
                             overview=frame["overview"], ranking=frame["ranking"], tiles=tiles))
    queue.sort(key=lambda s: -s["confidence"])
    for rank, sighting in enumerate(queue, 1):
        sighting["rank"] = rank
    return queue, coverage


def write_report(out, frames, queue, coverage, spent, stopped):
    for frame in frames:
        with Image.open(frame["path"]) as image:
            thumbnail = image.convert("RGB")
            thumbnail.thumbnail((1400, 1400))
            thumbnail.save(out / "frames" / f"{frame['name']}.jpg", quality=85)
    esc = html.escape
    cards = "".join(
        f'<li><a href="#{esc(s["frame"])}"><span class="photo"><img src="{esc(s["crop"])}" alt="Close look at the {esc(s["tile_name"])} tile of {esc(s["frame"])}">'
        f'<span class="pin" style="left:{100 * s["crop_x"]:.2f}%;top:{100 * s["crop_y"]:.2f}%"></span></span></a>'
        f'<p><b>#{s["rank"]}</b> {esc(s["frame"])} · {esc(s["tile_name"])} · confidence {s["confidence"]:.2f}</p></li>'
        for s in queue) or "<li><p>No sightings to review.</p></li>"
    maps = []
    for frame in coverage:
        cells = "".join(
            f'<span class="tile {t["status"].split(",")[0].replace(" ", "-")}" style="left:{100 * (t["tile"] % 3) / 3:.4f}%;top:{100 * (t["tile"] // 3) / 3:.4f}%">'
            f'<em>{esc(t["status"])}</em></span>' for t in frame["tiles"])
        pins = "".join(
            f'<span class="pin" style="left:{100 * s["x"] / frame["width"]:.2f}%;top:{100 * s["y"] / frame["height"]:.2f}%"></span>'
            for s in queue if s["frame"] == frame["frame"])
        unchecked = sum(t["status"] == "not checked" for t in frame["tiles"])
        if frame["overview"] == "done":
            note = f"{unchecked} of 9 tiles never got a close look."
        else:
            note = "Awaiting an overview." if frame["overview"] == "awaiting overview" else "Ember's overview could not be read, so no tile got a close look."
        maps.append(f'<section id="{esc(frame["frame"])}"><h3>{esc(frame["frame"])}</h3><p>{note}</p>'
                    f'<div class="photo"><img src="frames/{esc(frame["frame"])}.jpg" alt="{esc(frame["frame"])} with its coverage map">{cells}{pins}</div></section>')
    status = f"Stopped early: {esc(stopped)}." if stopped else "Finished."
    (out / "report.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reviewer queue · Open Water Search</title>
<style>
:root {{ color: #172f2e; background: #f5f3eb; font: 16px/1.5 system-ui, sans-serif; }}
body {{ margin: 0 auto; padding: 1.5rem; max-width: 80rem; }}
h1 {{ font: 400 2.4rem/1.1 Georgia, serif; margin: 0 0 .4rem; }}
h2 {{ margin: 2rem 0 .3rem; }} h3 {{ margin: 1.4rem 0 .2rem; }}
p {{ margin: .2rem 0 .6rem; max-width: 70ch; }}
a {{ color: #1b594c; }}
.muted {{ color: #48605b; }}
.queue {{ list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr)); gap: 1rem; }}
.queue a {{ display: block; }}
.photo {{ position: relative; display: block; background: #203e38; }}
.photo img {{ display: block; width: 100%; height: auto; }}
.pin {{ position: absolute; width: 18px; height: 18px; transform: translate(-50%, -50%); border: 3px solid #fff; border-radius: 50%; box-shadow: 0 0 0 1px #172f2e; }}
.tile {{ position: absolute; width: 33.3333%; height: 33.3333%; box-sizing: border-box; border: 1px solid #f5f3eb80; }}
.tile em {{ position: absolute; left: 4px; bottom: 4px; font: 600 .72rem/1.2 system-ui; font-style: normal; color: #172f2e; background: #f5f3ebd9; padding: .1rem .3rem; }}
.maps {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 32rem), 1fr)); gap: 0 1.5rem; }}
.tile.not-checked {{ background: #0f1f1d59; }}
.tile.not-checked em {{ background: #0f1f1d; color: #f5f3eb; }}
.tile.flagged {{ border: 3px solid #ffdd75; }}
.tile.checked {{ border: 2px solid #8ce8ec; }}
.tile.unreadable {{ border: 2px dashed #ff8a3d; }}
</style></head><body>
<h1>Reviewer queue</h1>
<p class="muted">{len(frames)} frames · {len(queue)} sightings to review · {dollars(spent)} spent on Muse Ember. {status}</p>
<p>Each card shows the close look Ember received, with its mark. Open a card to see that mark on the full frame. Water Ember checked without reporting anyone can still hold a swimmer, and shaded tiles never got a close look.</p>
<h2>Sightings, highest confidence first</h2>
<ol class="queue">{cards}</ol>
<h2>Coverage map</h2>
<p>Yellow tiles hold a sighting. Blue tiles were checked with nothing reported. Shaded tiles are water nobody has looked at closely yet.</p>
<div class="maps">{"".join(maps)}</div>
</body></html>
""")


def main():
    parser = argparse.ArgumentParser(description="Search drone frames for swimmers with Muse Ember.")
    parser.add_argument("frames", type=Path, help="folder of .jpg, .jpeg or .png drone frames")
    parser.add_argument("--out", type=Path, required=True, help="new folder for the results")
    parser.add_argument("--budget", type=float, default=0.05, help="most to spend on Ember, in dollars (default 0.05)")
    parser.add_argument("--looks", type=int, default=2, choices=range(0, 10), metavar="0-9",
                        help="close looks per frame after its overview (default 2)")
    parser.add_argument("--key-file", type=Path, help="file holding the Meta Model API key, instead of MODEL_API_KEY")
    args = parser.parse_args()
    if args.key_file:
        os.environ["MODEL_API_KEY"] = args.key_file.read_text().strip()
    if not os.environ.get("MODEL_API_KEY"):
        raise SystemExit("Set MODEL_API_KEY or pass --key-file.")
    if not 0 < args.budget <= 9:
        raise SystemExit("--budget must be more than $0 and at most $9.")
    frames = load_frames(args.frames)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "crops").mkdir()
    (args.out / "frames").mkdir()
    search = Search(Meta(), round(args.budget * NANO), args.out)
    stopped = None
    try:
        run(search, frames, args.looks)
    except OutOfBudget:
        stopped = "the next request could have exceeded the budget"
    except Exception as error:
        stopped = f"{type(error).__name__}: {error}"
    queue, coverage = summarize(frames)
    (args.out / "queue.json").write_text(json.dumps(queue, indent=2))
    (args.out / "coverage.json").write_text(json.dumps(coverage, indent=2))
    write_report(args.out, frames, queue, coverage, search.spent, stopped)
    ending = "Stopped early: " + stopped if stopped else "Finished."
    print(f"{len(frames)} frames, {len(queue)} sightings, {dollars(search.spent)} spent. {ending} Open {args.out / 'report.html'}")


if __name__ == "__main__":
    main()
