"""Search a flight of drone photos for swimmers with Muse Ember.

    MODEL_API_KEY=... python open_water_search.py FRAMES_DIR --out RESULTS_DIR --budget 0.05

FRAMES_DIR holds the flight's photos, ordered in time by file name. Every frame first gets one
overview, in which Ember ranks the nine tiles of a 3 x 3 grid. Then each frame gets close looks at its
top-ranked tiles, one round at a time, until the per-frame look count or the spending cap runs out. The
worst-case cost of every request is reserved against the spending cap before it is sent.

Up to eight requests run at once (--parallel). Requests are spaced out when Meta's rate-limit headers
run low, and after a 429 the tool waits at least the Retry-After time, then backs off with jitter.

RESULTS_DIR receives:
  search-record.json  the search record: every possible sighting, the coverage timeline of every tile of
                      every frame, every Ember call with its tokens and cost, and how the run ended
  report.html         the reviewer queue and a coverage map of every frame, built from the search record
  queue.json          the reviewer queue: ranked sightings, up to five per frame, built from the search record
  coverage.json       the coverage timeline from the search record: per frame, the tiles Ember checked,
                      flagged, could not read, or never reached
  calls.jsonl         every Ember call, written as it happens

The prompts, image preparation, output limit and answer readers are the ones used in the November 23
30-frame run and its validation repeat.
"""
import argparse
import base64
import html
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from itertools import groupby
from pathlib import Path

from PIL import Image

from runner import INSPECT, LIMIT, MODEL, NANO, OVERVIEW, Meta, interpret, prepare, price, rectangle
from score import grid_points

TILE_NAMES = ["top left", "top center", "top right", "middle left", "center",
              "middle right", "bottom left", "bottom center", "bottom right"]
REVIEW_LIMIT = 5
FAILURE_LIMIT = 10
# After a 429: wait out Retry-After, then back off from half a second, doubling on each further 429.
FIRST_BACKOFF = 0.5
RATE_LIMIT_TRIES = 8
RATE_LIMIT_HEADERS = dict(limit_requests="x-ratelimit-limit-requests", remaining_requests="x-ratelimit-remaining-requests",
                          limit_tokens="x-ratelimit-limit-tokens", remaining_tokens="x-ratelimit-remaining-tokens")


class OutOfBudget(Exception):
    pass


class Stopped(Exception):
    """Another request ended the run before this one was sent."""


class RateLimited(Exception):
    """Meta answered 429. retry_after is its Retry-After header in seconds, or None without one."""

    def __init__(self, retry_after):
        super().__init__(f"429, Retry-After {retry_after}")
        self.retry_after = retry_after


class Ember(Meta):
    """The Meta client for this command. A 429 raises RateLimited for the search to wait out, in place of
    runner.Meta's single fixed retry, and limits holds the rate-limit headers of the latest reply."""

    limits = None

    def post(self, route, payload):
        request = urllib.request.Request("https://api.meta.ai/v1/responses" + route, data=json.dumps(payload).encode(),
                                         headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        try:
            with self.client.open(request, timeout=90) as response:
                values = {key: response.headers.get(name, "") for key, name in RATE_LIMIT_HEADERS.items()}
                if all(value.isdigit() for value in values.values()):
                    self.limits = {key: int(value) for key, value in values.items()}
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429:
                raise
            wait = error.headers.get("Retry-After", "")
            raise RateLimited(int(wait) if wait.isdigit() else None) from error


def spacing(limits):
    """Seconds between requests once a rate-limit header shows less than a tenth left: enough for what is
    left to last a minute. Each request may use up to LIMIT output tokens."""
    if limits is None:
        return 0
    if (limits["remaining_requests"] >= limits["limit_requests"] / 10
            and limits["remaining_tokens"] >= limits["limit_tokens"] / 10):
        return 0
    requests_left = min(limits["remaining_requests"], limits["remaining_tokens"] // LIMIT)
    return min(60 / max(requests_left, 1), 60)


def dollars(nanodollars):
    return "$" + format(nanodollars / NANO, ".4f")


class Search:
    def __init__(self, api, budget_nano, out, parallel):
        self.api = api
        self.budget = budget_nano
        self.spent = 0
        self.reserved = 0
        self.out = out
        self.parallel = parallel
        self.calls = []
        self.log = (out / "calls.jsonl").open("a")
        self.failures_in_a_row = 0
        # Guards the money, the request order, the pacing and the shared records across request threads.
        self.lock = threading.Condition()
        self.next_turn = 0
        self.stopped = False
        self.next_send = 0

    def ask_all(self, requests):
        """Send each (frame, tile) request, up to parallel at once, and wait for all of them.

        Calls enter the search record in request order, whatever order they finish in. If any request
        failed or met the spending cap, raise what the first of them in request order raised.
        """
        first_call = len(self.calls)
        self.next_turn = 0
        with ThreadPoolExecutor(self.parallel) as pool:
            futures = [pool.submit(self.ask, frame, tile, turn) for turn, (frame, tile) in enumerate(requests)]
        turn_of = {(frame["name"], tile): turn for turn, (frame, tile) in enumerate(requests)}
        self.calls[first_call:] = sorted(self.calls[first_call:], key=lambda call: turn_of[call["frame"], call["tile"]])
        errors = [future.exception() for future in futures if future.exception() is not None]
        errors = [error for error in errors if not isinstance(error, Stopped)]
        if errors:
            raise errors[0]

    def ask(self, frame, tile, turn):
        """Send one overview (tile -1) or close look and store its answer in the frame. Any error stops the run."""
        try:
            self.send_and_read(frame, tile, turn)
        except Exception:
            with self.lock:
                self.stopped = True
                self.lock.notify_all()
            raise

    def send_and_read(self, frame, tile, turn):
        rect = rectangle(frame["width"], frame["height"], tile)
        image = prepare(frame["path"], rect)
        prompt = OVERVIEW if tile == -1 else INSPECT
        body = {"model": MODEL, "reasoning": {"effort": "minimal"}, "max_output_tokens": LIMIT,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}]}]}
        worst = price(self.within_rate_limits(self.api.count, body), 0, LIMIT)
        self.reserve(turn, worst)
        started = time.time()
        reply = self.within_rate_limits(self.api.generate, body)
        finished = time.time()
        usage = reply["usage"]
        paid = price(usage["input_tokens"], usage["input_tokens_details"]["cached_tokens"], usage["output_tokens"])
        event = interpret(dict(rect=rect, response=reply, started=started, finished=finished), tile)
        converted = grid_points(dict(tile=tile, evidence=event))
        if converted is not None:
            event.pop("failure")
            event["points"] = converted
        call = dict(frame=frame["name"], tile=tile, paid_nanodollars=paid, usage=usage,
                    seconds=round(finished - started, 3), answer=event)
        if tile >= 0:
            (self.out / "crops" / f"{frame['name']}-t{tile}.jpg").write_bytes(image)
            frame["tiles"][tile] = event.get("points")
        else:
            frame["ranking"] = event.get("tiles", [])
            frame["overview"] = "done" if frame["ranking"] else "unreadable"
        with self.lock:
            self.reserved -= worst
            self.spent += paid
            self.lock.notify_all()
            self.calls.append(call)
            self.log.write(json.dumps(call) + "\n")
            self.log.flush()
            self.failures_in_a_row = self.failures_in_a_row + 1 if "failure" in event else 0
            if self.failures_in_a_row >= FAILURE_LIMIT:
                raise RuntimeError(f"{FAILURE_LIMIT} unreadable answers in a row")

    def reserve(self, turn, worst):
        """Reserve a request's worst-case cost against the spending cap, in request order.

        When the worst case does not fit beside the requests in flight, wait for them to finish. Stop once it
        does not fit with nothing in flight, which is where a run sending one request at a time would stop.
        """
        with self.lock:
            self.lock.wait_for(lambda: self.stopped or (self.next_turn == turn and (
                self.reserved == 0 or self.spent + self.reserved + worst <= self.budget)))
            if self.stopped:
                raise Stopped()
            if self.spent + worst > self.budget:
                raise OutOfBudget()
            self.reserved += worst
            self.next_turn += 1
            self.lock.notify_all()

    def within_rate_limits(self, method, body):
        """Call Ember, spacing requests out when the rate-limit headers run low. After a 429, every request
        waits at least Retry-After, then a back-off that doubles with each 429 this request meets."""
        for attempt in range(RATE_LIMIT_TRIES):
            with self.lock:
                now = time.monotonic()
                send_at = max(now, self.next_send)
                self.next_send = send_at + spacing(self.api.limits)
            time.sleep(send_at - now)
            try:
                return method(body)
            except RateLimited as limited:
                backoff = FIRST_BACKOFF * 2 ** attempt * random.uniform(0.5, 1.5)
                with self.lock:
                    self.next_send = max(self.next_send, time.monotonic() + (limited.retry_after or 0) + backoff)
        raise RuntimeError(f"Meta answered 429 to {RATE_LIMIT_TRIES} tries in a row")


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
    search.ask_all([(frame, -1) for frame in frames])
    for round_number in range(looks):
        search.ask_all([(frame, frame["ranking"][round_number]) for frame in frames
                        if round_number < len(frame["ranking"])])


def search_record(flight, settings, frames, search, ending, seconds):
    """Everything the run found and spent for the flight. The other results are views of this record.

    Sightings are in pixels of the original frame, in flight order and then tile order. Photos per minute
    counts the frames that got their overview, over the seconds the search ran.
    """
    sightings, coverage_timeline = [], []
    for frame in frames:
        tiles = []
        for tile in range(9):
            if tile not in frame["tiles"]:
                status = "not checked"
            elif frame["tiles"][tile] is None:
                status = "unreadable"
            else:
                points = frame["tiles"][tile]
                status = "flagged" if points else "checked, no sighting"
                sightings += [dict(frame=frame["name"], tile=tile, x=x, y=y, confidence=c,
                                   crop=f"crops/{frame['name']}-t{tile}.jpg")
                              for x, y, c in points]
            tiles.append(dict(tile=tile, name=TILE_NAMES[tile], status=status))
        coverage_timeline.append(dict(frame=frame["name"], width=frame["width"], height=frame["height"],
                                      overview=frame["overview"], ranking=frame["ranking"], tiles=tiles))
    photos = sum(frame["overview"] != "awaiting overview" for frame in frames)
    return dict(flight=dict(source=str(flight)), settings=settings, coverage_timeline=coverage_timeline,
                sightings=sightings, calls=search.calls, spent_nanodollars=search.spent, ending=ending,
                seconds=round(seconds, 3), photos_per_minute=round(photos * 60 / seconds, 1))


def reviewer_queue(record):
    """Up to five sightings per frame, ranked across the flight by confidence."""
    sizes = {frame["frame"]: (frame["width"], frame["height"]) for frame in record["coverage_timeline"]}
    queue = []
    for name, sightings in groupby(record["sightings"], key=lambda s: s["frame"]):
        for s in sorted(sightings, key=lambda s: -s["confidence"])[:REVIEW_LIMIT]:
            left, top, right, bottom = rectangle(*sizes[name], s["tile"])
            queue.append(dict(frame=name, tile=s["tile"], tile_name=TILE_NAMES[s["tile"]],
                              x=round(s["x"], 1), y=round(s["y"], 1), confidence=s["confidence"], crop=s["crop"],
                              crop_x=(s["x"] - left) / (right - left), crop_y=(s["y"] - top) / (bottom - top)))
    queue.sort(key=lambda s: -s["confidence"])
    for rank, sighting in enumerate(queue, 1):
        sighting["rank"] = rank
    return queue


def save_frames(out, frames):
    """Save a reduced copy of each frame for the report page."""
    for frame in frames:
        with Image.open(frame["path"]) as image:
            thumbnail = image.convert("RGB")
            thumbnail.thumbnail((1400, 1400))
            thumbnail.save(out / "frames" / f"{frame['name']}.jpg", quality=85)


def write_report(out, record):
    queue = reviewer_queue(record)
    coverage = record["coverage_timeline"]
    stopped = record["ending"]["reason"]
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
<p class="muted">{len(coverage)} frames · {len(queue)} sightings to review · {dollars(record["spent_nanodollars"])} spent on Muse Ember. {status}</p>
<p>Each card shows the close look Ember received, with its mark. Open a card to see that mark on the full frame. Water Ember checked without reporting anyone can still hold a swimmer, and shaded tiles never got a close look.</p>
<h2>Sightings, highest confidence first</h2>
<ol class="queue">{cards}</ol>
<h2>Coverage map</h2>
<p>Yellow tiles hold a sighting. Blue tiles were checked with nothing reported. Shaded tiles are water nobody has looked at closely yet.</p>
<div class="maps">{"".join(maps)}</div>
</body></html>
""")


def main(arguments=None, api=None):
    """Run the command. Offline tests pass a simulated Ember as api; otherwise it calls Meta with MODEL_API_KEY."""
    parser = argparse.ArgumentParser(description="Search drone frames for swimmers with Muse Ember.")
    parser.add_argument("frames", type=Path, help="folder of .jpg, .jpeg or .png drone frames")
    parser.add_argument("--out", type=Path, required=True, help="new folder for the results")
    parser.add_argument("--budget", type=float, default=0.05, help="most to spend on Ember, in dollars (default 0.05)")
    parser.add_argument("--looks", type=int, default=2, choices=range(0, 10), metavar="0-9",
                        help="close looks per frame after its overview (default 2)")
    parser.add_argument("--parallel", type=int, default=8, choices=range(1, 9), metavar="1-8",
                        help="most requests to Ember at once (default 8)")
    parser.add_argument("--key-file", type=Path, help="file holding the Meta Model API key, instead of MODEL_API_KEY")
    args = parser.parse_args(arguments)
    if api is None:
        if args.key_file:
            os.environ["MODEL_API_KEY"] = args.key_file.read_text().strip()
        if not os.environ.get("MODEL_API_KEY"):
            raise SystemExit("Set MODEL_API_KEY or pass --key-file.")
        api = Ember()
    if not 0 < args.budget <= 9:
        raise SystemExit("--budget must be more than $0 and at most $9.")
    frames = load_frames(args.frames)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "crops").mkdir()
    (args.out / "frames").mkdir()
    budget = round(args.budget * NANO)
    search = Search(api, budget, args.out, args.parallel)
    ending = dict(outcome="finished", reason=None)
    started = time.monotonic()
    try:
        run(search, frames, args.looks)
    except OutOfBudget:
        ending = dict(outcome="spending cap", reason="the next request could have exceeded the budget")
    except Exception as error:
        ending = dict(outcome="failed", reason=f"{type(error).__name__}: {error}")
    seconds = time.monotonic() - started
    search.log.close()
    settings = dict(model=MODEL, looks=args.looks, parallel=args.parallel, spending_cap_nanodollars=budget)
    record = search_record(args.frames, settings, frames, search, ending, seconds)
    (args.out / "search-record.json").write_text(json.dumps(record, indent=2))
    queue = reviewer_queue(record)
    (args.out / "queue.json").write_text(json.dumps(queue, indent=2))
    (args.out / "coverage.json").write_text(json.dumps(record["coverage_timeline"], indent=2))
    save_frames(args.out, frames)
    write_report(args.out, record)
    how_it_ended = "Stopped early: " + ending["reason"] if ending["reason"] else "Finished."
    print(f"{len(frames)} frames, {len(queue)} sightings, {dollars(search.spent)} spent. {how_it_ended} "
          f"Search record: {args.out / 'search-record.json'}. Open {args.out / 'report.html'}")
    # A budget stop is a normal ending. A failed request is not, so scripts and agents can tell from the exit status.
    if ending["outcome"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
