"""Search a flight of drone photos for swimmers with Muse Ember.

    MODEL_API_KEY=... python open_water_search.py FRAMES_DIR --out RESULTS_DIR --budget 0.05

FRAMES_DIR holds the flight's photos, ordered in time by file name. Every frame first gets one
overview, in which Ember ranks the nine tiles of a 3 x 3 grid. Then each frame gets close looks at its
top-ranked tiles, one round at a time, until the per-frame look count or the spending cap runs out. The
worst-case cost of every request is checked against the spending cap before it is sent.

RESULTS_DIR receives:
  search-record.json  the search record: every possible sighting, the possible people they merge into with
                      a handoff message for each, the coverage timeline of every tile of every frame, every
                      Ember call with its tokens and cost, and how the run ended
  report.html         the reviewer queue and a coverage map of every frame, built from the search record
  queue.json          the reviewer queue: ranked sightings, up to five per frame, built from the search record
  coverage.json       the coverage timeline from the search record: per frame, the tiles Ember checked,
                      flagged, could not read, or never reached
  calls.jsonl         every Ember call, written as it happens

The flight holds one frame per second. Sightings in frames at most two seconds apart and within 10% of the
frame width of each other merge into one possible person. The run prints each possible person's handoff
message, which code writes from the search record without calling Ember.

The prompts, image preparation, output limit and answer readers are the ones used in the November 23
30-frame run and its validation repeat.

--format grounding asks for close-look marks in Meta's grounding format instead: points on a 0-1,000 grid over
the image Ember received, forced into a JSON schema by structured output. Overviews keep the frozen prompt.

--positions FILE gives the drone's latitude and longitude for the frames that have them, as JSON keyed by frame
name (write_positions.py writes one for SeaDronesSee frames). Handoff messages then give the drone position at
sighting, and the report maps where the drone was. Frames without position data get no coordinates. Without the
file, the search record says position data was unavailable and the report shows no map.
"""
import argparse
import base64
import html
import json
import math
import os
import time
from itertools import groupby
from pathlib import Path

from PIL import Image

import grounding_format
from runner import INSPECT, LIMIT, MODEL, NANO, OVERVIEW, Meta, interpret, prepare, price, rectangle
from score import grid_points

TILE_NAMES = ["top left", "top center", "top right", "middle left", "center",
              "middle right", "bottom left", "bottom center", "bottom right"]
REVIEW_LIMIT = 5
FAILURE_LIMIT = 10
# Sightings merge into one possible person when they are at most this many seconds apart
# and within this fraction of the frame width of each other.
MERGE_SECONDS = 2
MERGE_DISTANCE = 0.1
# Metres per degree of latitude, and per degree of longitude at the equator.
METRES_PER_DEGREE_NORTH = 110_574
METRES_PER_DEGREE_EAST = 111_320


class OutOfBudget(Exception):
    pass


def dollars(nanodollars):
    return "$" + format(nanodollars / NANO, ".4f")


class Search:
    def __init__(self, api, budget_nano, out, grounding=False):
        self.api = api
        self.budget = budget_nano
        self.grounding = grounding
        self.spent = 0
        self.out = out
        self.calls = []
        self.log = (out / "calls.jsonl").open("a")
        self.failures_in_a_row = 0

    def ask(self, frame, tile):
        """Send one overview (tile -1) or close look, and return the read answer."""
        rect = rectangle(frame["width"], frame["height"], tile)
        image = prepare(frame["path"], rect)
        grounding = self.grounding and tile >= 0
        prompt = OVERVIEW if tile == -1 else grounding_format.INSPECT if grounding else INSPECT
        body = {"model": MODEL, "reasoning": {"effort": "minimal"}, "max_output_tokens": LIMIT,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}]}]}
        if grounding:
            body["text"] = {"format": grounding_format.MARKS}
        input_tokens = self.api.count(body)
        if grounding:
            # Meta's input-token count leaves out the schema, so count each of its characters as a token. That can
            # only overestimate, which keeps the spending cap a guarantee.
            input_tokens += len(json.dumps(body["text"]))
        worst = price(input_tokens, 0, LIMIT)
        if self.spent + worst > self.budget:
            raise OutOfBudget()
        started = time.time()
        reply = self.api.generate(body)
        finished = time.time()
        usage = reply["usage"]
        paid = price(usage["input_tokens"], usage["input_tokens_details"]["cached_tokens"], usage["output_tokens"])
        self.spent += paid
        answered = dict(rect=rect, response=reply, started=started, finished=finished)
        if grounding:
            event = grounding_format.read_marks(answered)
        else:
            event = interpret(answered, tile)
            converted = grid_points(dict(tile=tile, evidence=event))
            if converted is not None:
                event.pop("failure")
                event["points"] = converted
        call = dict(frame=frame["name"], tile=tile, paid_nanodollars=paid, usage=usage,
                    seconds=round(finished - started, 3), answer=event)
        self.calls.append(call)
        self.log.write(json.dumps(call) + "\n")
        self.log.flush()
        self.failures_in_a_row = self.failures_in_a_row + 1 if "failure" in event else 0
        if self.failures_in_a_row >= FAILURE_LIMIT:
            raise RuntimeError(f"{FAILURE_LIMIT} unreadable answers in a row")
        if tile >= 0:
            (self.out / "crops" / f"{frame['name']}-t{tile}.jpg").write_bytes(image)
        return event


def load_frames(folder):
    """The flight's frames in time order. A flight holds one frame per second, so each frame's place is its second."""
    frames = []
    for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")):
        with Image.open(path) as image:
            width, height = image.size
        frames.append(dict(path=path, name=path.stem, second=len(frames), width=width, height=height,
                           overview="awaiting overview", ranking=[], tiles={}))
    if not frames:
        raise SystemExit(f"No .jpg, .jpeg or .png frames in {folder}")
    return frames


def read_positions(path, frames):
    """Give each frame the drone's position from the operator's position file, where the file has one.

    The file maps frame names to the drone's latitude and longitude in decimal degrees, and may keep the source
    metadata alongside them. A frame that is missing from the file or null in it has no position data.
    """
    given = json.loads(path.read_text())["frames"]
    for frame in frames:
        position = given.get(frame["name"])
        if position is None:
            continue
        latitude, longitude = position.get("latitude"), position.get("longitude")
        if not (isinstance(latitude, (int, float)) and isinstance(longitude, (int, float))
                and -90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise SystemExit(f"{path}: {frame['name']} needs a latitude from -90 to 90 and a longitude from -180 to 180.")
        frame["drone_position"] = position


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


def search_record(flight, settings, frames, search, ending):
    """Everything the run found and spent for the flight. The other results are views of this record.

    Sightings are in pixels of the original frame, in flight order and then tile order.
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
                sightings += [dict(frame=frame["name"], second=frame["second"], tile=tile, x=x, y=y, confidence=c,
                                   crop=f"crops/{frame['name']}-t{tile}.jpg")
                              for x, y, c in points]
            tiles.append(dict(tile=tile, name=TILE_NAMES[tile], status=status))
        entry = dict(frame=frame["name"], width=frame["width"], height=frame["height"],
                     overview=frame["overview"], ranking=frame["ranking"], tiles=tiles)
        if "drone_position" in frame:
            entry["drone_position"] = frame["drone_position"]
        coverage_timeline.append(entry)
    placed = sum("drone_position" in frame for frame in coverage_timeline)
    position_data = f"drone position for {placed} of {len(frames)} frames" if placed else "unavailable"
    return dict(flight=dict(source=str(flight), position_data=position_data), settings=settings,
                coverage_timeline=coverage_timeline,
                sightings=sightings, possible_people=possible_people(sightings, coverage_timeline),
                calls=search.calls, spent_nanodollars=search.spent, ending=ending)


def possible_people(sightings, coverage_timeline):
    """Merge the flight's sightings into possible people, numbered in the order they were first seen.

    A sighting joins the nearest possible person last seen one or two seconds earlier within 10% of the frame
    width of that last sighting. Otherwise it starts a new possible person, so a gap of more than two seconds
    splits one. A possible person takes at most one sighting per second, so two sightings in one frame stay two
    possible people. Within a second, the most confident sightings join first.
    """
    widths = {frame["frame"]: frame["width"] for frame in coverage_timeline}
    people = []
    for second, in_this_second in groupby(sightings, key=lambda s: s["second"]):
        can_join = [person for person in people if second - person[-1]["second"] <= MERGE_SECONDS]
        for sighting in sorted(in_this_second, key=lambda s: -s["confidence"]):
            reach = MERGE_DISTANCE * widths[sighting["frame"]]
            near = [person for person in can_join if separation(person[-1], sighting) <= reach]
            if near:
                person = min(near, key=lambda person: separation(person[-1], sighting))
                can_join.remove(person)
            else:
                person = []
                people.append(person)
            person.append(sighting)
    merged = []
    timeline = {frame["frame"]: frame for frame in coverage_timeline}
    for number, person in enumerate(people, 1):
        last = person[-1]
        # Where the possible person was last seen, in pixels of that frame.
        position = dict(frame=last["frame"], x=last["x"], y=last["y"], section=TILE_NAMES[last["tile"]])
        drone = timeline[last["frame"]].get("drone_position")
        if drone:
            position["drone_position_at_sighting"] = dict(latitude=drone["latitude"], longitude=drone["longitude"])
        possible_person = dict(number=number, first_seen_second=person[0]["second"], last_seen_second=last["second"],
                               first_frame=person[0]["frame"], last_frame=last["frame"], position=position,
                               confidence=max(s["confidence"] for s in person), sightings=person)
        possible_person["handoff_message"] = handoff_message(possible_person, coverage_timeline)
        merged.append(possible_person)
    return merged


def separation(first, second):
    return math.dist((first["x"], first["y"]), (second["x"], second["y"]))


def handoff_message(person, coverage_timeline):
    """The fixed-format message a dispatcher reads to a boat crew, written from the search record without Ember.

    A section whose close look could not be read counts as never searched.

    The flight data gives the drone's position but no camera field of view, and its altitude is measured from the
    takeoff point, so the person's own coordinates would be a guess. The message gives where the drone was.
    """
    position = person["position"]
    frame = next(frame for frame in coverage_timeline if frame["frame"] == position["frame"])
    never_searched = sum(tile["status"] in ("not checked", "unreadable") for tile in frame["tiles"])
    where = ""
    if "drone_position_at_sighting" in position:
        drone = position["drone_position_at_sighting"]
        where = (f" Drone position at sighting latitude {drone['latitude']:.5f}, longitude {drone['longitude']:.5f}."
                 " The person's own position could not be worked out from the flight data.")
    elif any("drone_position" in frame for frame in coverage_timeline):
        where = " No position data for that frame."
    return (f"Possible person {person['number']}. First seen {flight_time(person['first_seen_second'])}, "
            f"last seen {flight_time(person['last_seen_second'])} into the flight, "
            f"in the {position['section']} section of {position['frame']}.{where} "
            f"Confidence {person['confidence']:.2f}. {never_searched} of the 9 sections of that frame were never searched.")


def flight_time(second):
    return f"{second // 60}:{second % 60:02}"


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


def drone_positions(record):
    """The report's section on where the drone was, with a map only of the frames that have position data.

    The map is north up with no background. Distances come from a flat-earth approximation around the first
    position, which holds over the few kilometres of one flight.
    """
    placed = [frame for frame in record["coverage_timeline"] if "drone_position" in frame]
    if not placed:
        return "<h2>Drone positions</h2><p>No position data came with this flight, so this report shows no coordinates or map.</p>"
    origin = placed[0]["drone_position"]
    metres_per_degree_east = METRES_PER_DEGREE_EAST * math.cos(math.radians(origin["latitude"]))
    east = [(frame["drone_position"]["longitude"] - origin["longitude"]) * metres_per_degree_east for frame in placed]
    north = [(frame["drone_position"]["latitude"] - origin["latitude"]) * METRES_PER_DEGREE_NORTH for frame in placed]
    # Fit the positions into a 600 x 400 drawing with a 40-unit margin, showing at least 50 metres each way.
    scale = min(520 / max(max(east) - min(east), 50), 320 / max(max(north) - min(north), 50))
    middle_east, middle_north = (max(east) + min(east)) / 2, (max(north) + min(north)) / 2
    last_seen = {}
    for person in record["possible_people"]:
        last_seen.setdefault(person["position"]["frame"], []).append(str(person["number"]))
    plain, yellow = [], []
    for frame, metres_east, metres_north in zip(placed, east, north):
        x = 300 + (metres_east - middle_east) * scale
        y = 200 - (metres_north - middle_north) * scale
        if frame["frame"] in last_seen:
            yellow.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#ffdd75" stroke="#172f2e"><title>'
                          f'{html.escape(frame["frame"])}, possible person {", ".join(last_seen[frame["frame"]])}</title></circle>')
        else:
            plain.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#1b594c">'
                         f'<title>{html.escape(frame["frame"])}</title></circle>')
    missing = len(record["coverage_timeline"]) - len(placed)
    return (f'<h2>Drone positions</h2><p>Where the drone was for each frame with position data, north up. Yellow dots '
            f'mark the frames where a possible person was last seen. The positions span '
            f'{max(east) - min(east):,.0f} m east to west and {max(north) - min(north):,.0f} m north to south. '
            f'{missing} of {len(record["coverage_timeline"])} frames have no position data and are not on the map.</p>'
            f'<svg viewBox="0 0 600 400" role="img" aria-label="Drone positions, north up" '
            f'style="display: block; width: 100%; max-width: 50rem; background: #e6ebe3;">'
            f'{"".join(plain + yellow)}</svg>')


def write_report(out, record):
    queue = reviewer_queue(record)
    coverage = record["coverage_timeline"]
    has_positions = any("drone_position" in frame for frame in coverage)
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
        if "drone_position" in frame:
            drone = frame["drone_position"]
            note += f" Drone position latitude {drone['latitude']:.5f}, longitude {drone['longitude']:.5f}."
        elif has_positions:
            note += " No position data for this frame."
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
{drone_positions(record)}
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
    parser.add_argument("--format", choices=("frozen", "grounding"), default="frozen",
                        help="how close looks ask for marks: the frozen prompts of the published runs (default), "
                             "or Meta's 0-1,000 grounding format with a JSON schema")
    parser.add_argument("--key-file", type=Path, help="file holding the Meta Model API key, instead of MODEL_API_KEY")
    parser.add_argument("--positions", type=Path,
                        help="JSON file of the drone's latitude and longitude for each frame, keyed by frame name")
    args = parser.parse_args(arguments)
    if api is None:
        if args.key_file:
            os.environ["MODEL_API_KEY"] = args.key_file.read_text().strip()
        if not os.environ.get("MODEL_API_KEY"):
            raise SystemExit("Set MODEL_API_KEY or pass --key-file.")
        api = Meta()
    if not 0 < args.budget <= 9:
        raise SystemExit("--budget must be more than $0 and at most $9.")
    frames = load_frames(args.frames)
    if args.positions:
        read_positions(args.positions, frames)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "crops").mkdir()
    (args.out / "frames").mkdir()
    budget = round(args.budget * NANO)
    search = Search(api, budget, args.out, grounding=args.format == "grounding")
    ending = dict(outcome="finished", reason=None)
    try:
        run(search, frames, args.looks)
    except OutOfBudget:
        ending = dict(outcome="spending cap", reason="the next request could have exceeded the budget")
    except Exception as error:
        ending = dict(outcome="failed", reason=f"{type(error).__name__}: {error}")
    search.log.close()
    settings = dict(model=MODEL, looks=args.looks, format=args.format, spending_cap_nanodollars=budget)
    record = search_record(args.frames, settings, frames, search, ending)
    (args.out / "search-record.json").write_text(json.dumps(record, indent=2))
    queue = reviewer_queue(record)
    (args.out / "queue.json").write_text(json.dumps(queue, indent=2))
    (args.out / "coverage.json").write_text(json.dumps(record["coverage_timeline"], indent=2))
    save_frames(args.out, frames)
    write_report(args.out, record)
    for person in record["possible_people"]:
        print(person["handoff_message"])
    how_it_ended = "Stopped early: " + ending["reason"] if ending["reason"] else "Finished."
    print(f"{len(frames)} frames, {len(queue)} sightings, {dollars(search.spent)} spent. {how_it_ended} "
          f"Search record: {args.out / 'search-record.json'}. Open {args.out / 'report.html'}")
    # A budget stop is a normal ending. A failed request is not, so scripts and agents can tell from the exit status.
    if ending["outcome"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
