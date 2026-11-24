"""Have Muse Ember check a detector's candidate boxes, one request per photo, and score the ones it accepts.

    python3 probe/verify_candidates.py CANDIDATES INPUTS_MANIFEST SCORING_DIR --out OUT --budget 0.25 [--key-file KEY]

CANDIDATES is a detector's boxes.json (see detector/run_detector.py). For each photo, its swimmer boxes (class 0)
are taken in order of detector confidence, at most MAX_CANDIDATES of them. Each becomes a square crop centred on the
box, CROP_SCALE times its longer side and at least MIN_CROP pixels, sent to Ember at CROP_PIXELS square. One request
carries all of a photo's crops, numbered from 1, and structured output forces the answer into CHECKS: for every crop,
whether a person in the water is at its centre, a confidence and a few words saying what is there.

An accepted candidate becomes a sighting at its box's centre, ranked by Ember's confidence and then the detector's,
and probe/score.py's one scoring rule keeps the five best per photo. Before each request its worst-case cost is
reserved against --budget, so the run stops before crossing it. OUT gets checks.jsonl (every call as returned),
sightings.json, scorecard.json and summary.json.
"""
import argparse
import base64
import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from open_water_search import Ember, RateLimited, is_transient
from runner import LIMIT, MODEL, NANO, price
from score import groundtruth, score_sightings

MAX_CANDIDATES = 12
CROP_SCALE = 3
MIN_CROP = 96
CROP_PIXELS = 224
PROMPT = ("Each numbered image is a crop from a drone photo of open water, centred on something a detector flagged. "
          "For every crop, say whether a person in the water is at its centre, how confident you are from 0 to 1, "
          "and in a few words what is there.")
CHECKS = {"type": "json_schema", "name": "checks", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["crops"],
    "properties": {"crops": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["crop", "person", "confidence", "what"],
        "properties": {"crop": {"type": "integer"}, "person": {"type": "boolean"},
                       "confidence": {"type": "number"}, "what": {"type": "string"}}}}}}}


class OutOfBudget(Exception):
    pass


def candidates(photo):
    swimmers = [box for box in photo["boxes"] if box[5] == 0]
    return sorted(swimmers, key=lambda box: -box[4])[:MAX_CANDIDATES]


def crop(image, box):
    x1, y1, x2, y2 = box[:4]
    side = max(CROP_SCALE * max(x2 - x1, y2 - y1), MIN_CROP)
    side = min(side, image.width, image.height)
    left = min(max((x1 + x2) / 2 - side / 2, 0), image.width - side)
    top = min(max((y1 + y2) / 2 - side / 2, 0), image.height - side)
    region = image.crop((round(left), round(top), round(left + side), round(top + side)))
    buffer = io.BytesIO()
    region.resize((CROP_PIXELS, CROP_PIXELS), Image.Resampling.LANCZOS).save(buffer, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def request_body(image, boxes):
    content = [{"type": "input_text", "text": PROMPT}]
    for number, box in enumerate(boxes, 1):
        content += [{"type": "input_text", "text": f"Crop {number}:"}, {"type": "input_image", "image_url": crop(image, box)}]
    return {"model": MODEL, "reasoning": {"effort": "minimal"}, "max_output_tokens": LIMIT,
            "input": [{"role": "user", "content": content}], "text": {"format": CHECKS}}


def read_checks(reply, count):
    """Ember's verdict for each crop as (person, confidence, what), or None when the answer is not schema-shaped."""
    raw = "".join(part["text"] for item in reply["output"] for part in item.get("content", [])
                  if part["type"] == "output_text")
    try:
        crops = json.loads(raw)["crops"]
        verdicts = {int(c["crop"]): (bool(c["person"]), float(c["confidence"]), str(c["what"])) for c in crops}
    except (ValueError, KeyError, TypeError):
        return None
    return [verdicts.get(number) for number in range(1, count + 1)]


class Checker:
    def __init__(self, api, budget, log):
        self.api, self.budget, self.log = api, budget, log
        self.spent = self.reserved = 0
        self.lock = threading.Lock()

    def send(self, body):
        """One retry after a 429, timeout or dropped connection, as for every paid run in this project."""
        for attempt in range(2):
            try:
                return self.api.generate(body)
            except RateLimited as limited:
                if attempt == 1:
                    raise RuntimeError("Meta answered 429 twice")
                time.sleep((limited.retry_after or 0) + 0.5)
            except Exception as error:
                if not is_transient(error) or attempt == 1:
                    raise
                time.sleep(0.5)

    def check(self, photo, image_path):
        boxes = candidates(photo)
        with Image.open(image_path) as opened:
            body = request_body(opened.convert("RGB"), boxes)
        # Meta's token count leaves out the schema, so count each of its characters as a token.
        worst = price(self.api.count(body) + len(json.dumps(body["text"])), 0, LIMIT)
        with self.lock:
            if self.spent + self.reserved + worst > self.budget:
                raise OutOfBudget()
            self.reserved += worst
        try:
            reply = self.send(body)
        except Exception:
            with self.lock:
                self.reserved -= worst
                self.spent += worst  # a lost request may still be billed
            raise
        usage = reply["usage"]
        paid = price(usage["input_tokens"], usage["input_tokens_details"]["cached_tokens"], usage["output_tokens"])
        verdicts = read_checks(reply, len(boxes))
        with self.lock:
            self.reserved -= worst
            self.spent += paid
            self.log.write(json.dumps(dict(frame=photo["frame"], boxes=boxes, paid_nanodollars=paid, usage=usage,
                                           verdicts=verdicts, response=reply)) + "\n")
            self.log.flush()
        return boxes, verdicts


def sightings_from(boxes, verdicts):
    accepted = [(box, verdict) for box, verdict in zip(boxes, verdicts or []) if verdict and verdict[0]]
    accepted.sort(key=lambda pair: (-pair[1][1], -pair[0][4]))
    return [[(box[0] + box[2]) / 2, (box[1] + box[3]) / 2, verdict[1]] for box, verdict in accepted]


def main(arguments=None, api=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("inputs", type=Path, help="inputs manifest.json listing the photos")
    parser.add_argument("scoring", type=Path, help="scoring-only folder with manifest.json and labels/")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--budget", type=float, required=True, help="most to spend on Ember, in dollars")
    parser.add_argument("--parallel", type=int, default=8)
    parser.add_argument("--key-file", type=Path)
    args = parser.parse_args(arguments)
    if api is None:
        if args.key_file:
            os.environ["MODEL_API_KEY"] = args.key_file.read_text().strip()
        api = Ember()
    photos = json.loads(args.candidates.read_text())
    paths = {f["frame"]: args.inputs.parent / f["image"] for f in json.loads(args.inputs.read_text())["frames"]}
    args.out.mkdir(parents=True, exist_ok=False)
    to_check = [photo for photo in photos if candidates(photo)]
    with (args.out / "checks.jsonl").open("w") as log:
        checker = Checker(api, round(args.budget * NANO), log)
        with ThreadPoolExecutor(args.parallel) as pool:
            futures = {photo["frame"]: pool.submit(checker.check, photo, paths[photo["frame"]]) for photo in to_check}
        results, ending = {}, "finished"
        for frame, future in futures.items():
            try:
                results[frame] = future.result()
            except OutOfBudget:
                ending = "spending cap"
            except Exception as error:
                ending = f"failed: {type(error).__name__}: {error}"
    sightings = {photo["frame"]: sightings_from(*results.get(photo["frame"], ([], []))) for photo in photos}
    frames = [dict(frame=photo["frame"], width=photo["width"], height=photo["height"]) for photo in photos]
    card = score_sightings(sightings, frames, groundtruth(args.scoring, frames))
    summary = dict(model=MODEL, photos=len(photos), photos_checked=len(results),
                   photos_not_checked=len(to_check) - len(results),
                   candidates=sum(len(candidates(photo)) for photo in to_check), ending=ending,
                   spent_nanodollars=checker.spent,
                   settings=dict(max_candidates=MAX_CANDIDATES, crop_scale=CROP_SCALE, min_crop=MIN_CROP,
                                 crop_pixels=CROP_PIXELS, prompt=PROMPT))
    (args.out / "sightings.json").write_text(json.dumps(sightings, indent=1))
    (args.out / "scorecard.json").write_text(json.dumps(card, indent=2, sort_keys=True))
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"{len(results)} photos checked, {card['found']} of {card['appearances']} found, "
          f"{card['unmatched']} marks with no swimmer, {checker.spent / NANO:.4f} dollars spent, {ending}")
    if ending.startswith("failed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
