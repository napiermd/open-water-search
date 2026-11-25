"""Sort the real people Ember's check dismissed by what Ember said it saw, with where each person sat in the crop.

    python3 experiments/lost-people/dismissed-people/sort_dismissed.py [--sheets]

Reads sealed runs only and makes no Ember call. A flag sits on a person when its centre is inside a labelled person
box, the same match probe/score.py uses. For every such flag it records Ember's verdict and words, the detector's
confidence, and two measurements of the crop Ember was sent:

- offset: how far the labelled person's centre is from the crop's centre, as a share of the crop's side
  (0 is dead centre, 0.5 is the edge).
- pixels: the labelled person's longer side as Ember saw it in the 224-pixel crop.
- pushed_in: the flag sat so near the photo's edge that the crop could not be centred on it.
- people_in_crop: how many labelled people have their centre inside the crop.

Each dismissed flag gets one reason from Ember's words, by the keyword rules in reason(). dismissed.json lists every
one with its words so the sorting can be checked by eye. summary.json holds the counts per run and reason, and the
same two measurements for the flags Ember kept. --sheets also writes one image of example crops per reason from
the MOBDrone runs, which needs the photos linked in locally.
"""
import json
import math
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "probe"))
from flag_check import CROP_PIXELS, crop_square  # noqa: E402
from score import groundtruth  # noqa: E402

# name, checks or search record, inputs manifest (None for a live run's own frames), labels, photos
RUNS = [
    ("MOBDrone, first 300 frames", "runs/verify-check/mobdrone-300/checks-redacted.jsonl",
     "mobdrone/inputs/manifest.json", "mobdrone/scoring-only"),
    ("MOBDrone, second 300 frames", "runs/verify-mobdrone/run/checks-redacted.jsonl",
     "runs/verify-mobdrone/inputs/manifest.json", "runs/verify-mobdrone/scoring-only"),
    ("AFO, 300 photos", "runs/verify-afo/run/checks-redacted.jsonl",
     "runs/verify-afo/inputs/manifest.json", "runs/verify-afo/scoring-only"),
    ("Live clip, re-run", "runs/live-detector-check/search-record-redacted.json", None, "mobdrone/clip/scoring-only"),
    ("Live clip, first take", "runs/live-detector-check-first-take/search-record-redacted.json", None,
     "mobdrone/clip/scoring-only"),
]
SHEET_RUNS = RUNS[:2]

PERSON = r"\b(person|people|swimmers?|heads?|legs|paddlers?|kayakers?|waders|group|rider)\b"
PLACE = (r"\b(centre|center|centred|centered|edge|edges|between|around|offset|either side|above|below|left|right|top|"
         r"bottom|beside|off-centre|off-center)\b")
REASONS = [
    ("A person on land", r"\b(sand|beach|shore|shoreline|land|towel)\b"),
    ("An animal", r"\b(bird|bird-like|seagull|seabird|waterbird|duck|seal|dolphin|turtle|turtle-like|animal|fish|fin)\b"),
    ("A person, but away from the centre of the crop", None),  # a person word and a place word, see reason()
    ("A board, boat or float", r"\b(paddleboards?|board|boards|surfboard|boat|boats|raft|kayak|jet ski|watercraft|"
                               r"floats?|buoy|rope)\b"),
    ("Foam, a splash or a wake", r"\b(foam|splash|splashing|wake|wave|waves|wash|blur|blurry|disturbance|ripples)\b"),
    ("Empty water", r"\b(open water|empty water)\b"),
    ("An unclear object", None),  # everything else
]


def reason(what):
    """The reason for Ember's words, from the first rule in REASONS they meet."""
    words = re.sub(r"\bno (clear |centre |center )?person\b", "", what.lower())
    for name, pattern in REASONS:
        if name.startswith("A person, but"):
            if re.search(PERSON, words) and re.search(PLACE, words):
                return name
        elif pattern and re.search(pattern, words):
            return name
    return REASONS[-1][0]


def flags_of(path):
    """Every checked flag of a run as (frame, box, kept, Ember's confidence, Ember's words)."""
    if path.suffix == ".jsonl":
        for line in path.read_text().splitlines():
            row = json.loads(line)
            for box, verdict in zip(row["boxes"], row["verdicts"] or []):
                if verdict:
                    yield row["frame"], box, verdict[0], verdict[1], verdict[2]
    else:
        for second in json.loads(path.read_text())["coverage_timeline"]:
            for flag in second.get("flags", []):
                box = flag["box"] + [flag["detector_confidence"], 0]
                yield second["frame"], box, flag["status"] == "kept", flag["ember_confidence"], flag["what"]


def frames_of(run, inputs):
    if inputs:
        return json.loads((ROOT / inputs).read_text())["frames"]
    return [dict(frame=s["frame"], width=s["width"], height=s["height"], image=f"frames/{s['frame']}.jpg")
            for s in json.loads((ROOT / run).read_text())["coverage_timeline"]]


def measure(frame, box, labels):
    """The labelled person this flag sits on and how the crop shows them, or None if its centre is on nobody."""
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    people = [person for cls, person in labels if cls == 0]
    on = [person for person in people if person[0] <= x <= person[2] and person[1] <= y <= person[3]]
    if not on:
        return None
    person = min(on, key=lambda p: (p[2] - p[0]) * (p[3] - p[1]))
    left, top, right, bottom = crop_square(frame["width"], frame["height"], box)
    side = right - left
    offset = math.dist(((person[0] + person[2]) / 2, (person[1] + person[3]) / 2),
                       ((left + right) / 2, (top + bottom) / 2)) / side
    pixels = max(person[2] - person[0], person[3] - person[1]) / side * CROP_PIXELS
    pushed_in = math.dist((x, y), ((left + right) / 2, (top + bottom) / 2)) > 1
    in_crop = sum(left <= (p[0] + p[2]) / 2 <= right and top <= (p[1] + p[3]) / 2 <= bottom for p in people)
    return dict(offset=round(offset, 3), pixels=round(pixels, 1), pushed_in=pushed_in, people_in_crop=in_crop,
                person=[round(v, 1) for v in person])


def middle(values):
    return round(statistics.median(values), 3) if values else None


def shape(flags):
    """How the crops of these flags showed their people."""
    return dict(flags=len(flags), median_offset=middle([f["offset"] for f in flags]),
                median_pixels=middle([f["pixels"] for f in flags]),
                offset_over_a_quarter=sum(f["offset"] > 0.25 for f in flags),
                pushed_in=sum(f["pushed_in"] for f in flags),
                several_people_in_crop=sum(f["people_in_crop"] > 1 for f in flags))


def main(sheets):
    dismissed, summary = [], []
    for name, run, inputs, scoring in RUNS:
        frames = {f["frame"]: f for f in frames_of(run, inputs)}
        labels = groundtruth(ROOT / scoring, list(frames.values()))
        kept, counts, on_people, not_on_people = [], Counter(), 0, Counter()
        for frame, box, was_kept, confidence, what in flags_of(ROOT / run):
            measured = measure(frames[frame], box, labels[frame])
            if not measured:
                not_on_people["kept" if was_kept else "dismissed"] += 1
                continue
            on_people += 1
            if was_kept:
                kept.append(measured)
                continue
            why = reason(what)
            counts[why] += 1
            dismissed.append(dict(run=name, frame=frame, box=box[:4], detector_confidence=box[4],
                                  ember_confidence=confidence, what=what, reason=why, **measured,
                                  image=frames[frame]["image"], inputs=inputs or run))
        mine = [d for d in dismissed if d["run"] == name]
        summary.append(dict(
            run=name, flags_on_people=on_people, kept=len(kept), dismissed=len(mine),
            flags_on_nobody=dict(not_on_people),
            reasons={why: counts[why] for why, _ in REASONS},
            kept_shape=shape(kept), dismissed_shape=shape(mine)))
    by_reason = []
    for why, _ in REASONS:
        mine = [d for d in dismissed if d["reason"] == why]
        by_reason.append(dict(reason=why, **shape(mine),
                              median_detector_confidence=middle([d["detector_confidence"] for d in mine])))
    # The labelled box itself stays out of the published list, as labels stay out of the repository.
    (HERE / "dismissed.json").write_text(json.dumps(
        [{k: v for k, v in d.items() if k not in ("inputs", "person")} for d in dismissed], indent=1) + "\n")
    (HERE / "summary.json").write_text(json.dumps(dict(runs=summary, reasons=by_reason), indent=1) + "\n")
    print(json.dumps(dict(runs=summary, reasons=by_reason), indent=1))
    if sheets:
        write_sheets([d for d in dismissed if d["run"] in {name for name, *_ in SHEET_RUNS}])


def write_sheets(dismissed):
    """One image per reason: up to eight crops as Ember saw them, the labelled person outlined, Ember's words below."""
    from PIL import Image, ImageDraw

    for number, (why, _) in enumerate(REASONS, 1):
        mine = sorted((d for d in dismissed if d["reason"] == why), key=lambda d: (d["run"], d["frame"]))[:8]
        if not mine:
            continue
        scale, caption = 2, 44
        sheet = Image.new("RGB", (len(mine) * (CROP_PIXELS * scale + 8) + 8, CROP_PIXELS * scale + caption + 16), "white")
        draw = ImageDraw.Draw(sheet)
        for column, d in enumerate(mine):
            with Image.open((ROOT / d["inputs"]).parent / d["image"]) as photo:
                left, top, right, bottom = crop_square(photo.width, photo.height, d["box"])
                crop = photo.convert("RGB").crop((left, top, right, bottom))
            crop = crop.resize((CROP_PIXELS, CROP_PIXELS), Image.Resampling.LANCZOS)
            crop = crop.resize((CROP_PIXELS * scale, CROP_PIXELS * scale), Image.Resampling.NEAREST)
            x = 8 + column * (CROP_PIXELS * scale + 8)
            sheet.paste(crop, (x, 8))
            zoom = CROP_PIXELS * scale / (right - left)
            px1, py1, px2, py2 = [(v - o) * zoom for v, o in zip(d["person"], (left, top, left, top))]
            draw.rectangle((x + px1 - 3, 8 + py1 - 3, x + px2 + 3, 8 + py2 + 3), outline="white", width=1)
            words = d["what"] if len(d["what"]) <= 70 else d["what"][:67] + "..."
            lines = [words[:36].rsplit(" ", 1)[0], words[len(words[:36].rsplit(" ", 1)[0]):].strip()] if len(words) > 36 else [words]
            for row, line in enumerate(lines):
                draw.text((x, 8 + CROP_PIXELS * scale + 6 + 14 * row), line, fill="black")
        sheet.save(HERE / f"examples-{number}-{re.sub('[^a-z]+', '-', why.lower()).strip('-')}.jpg", quality=88)


if __name__ == "__main__":
    main("--sheets" in sys.argv)
