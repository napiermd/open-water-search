"""Ember's check of a detector's flags: the crops, the request and how its answer is read.

Shared by probe/verify_candidates.py, which ran the sealed tests in runs/verify-check, runs/verify-confirm and
runs/verify-mobdrone, and by open_water_search.py --mode detector-check. Both send exactly these requests.

A frame's flags are its detector swimmer boxes (class 0), in order of detector confidence, at most MAX_CANDIDATES.
Each becomes a square crop centred on the box, CROP_SCALE times its longer side and at least MIN_CROP pixels, sent
at CROP_PIXELS square. One request carries all of a frame's crops, numbered from 1, and structured output forces the
answer into CHECKS: for every crop, whether a person in the water is at its centre, a confidence and a few words
saying what is there.
"""
import base64
import io
import json

from PIL import Image

from runner import LIMIT, MODEL

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


def candidates(photo):
    """The photo's flags: its swimmer boxes [x1, y1, x2, y2, confidence, class], most confident first."""
    swimmers = [box for box in photo["boxes"] if box[5] == 0]
    return sorted(swimmers, key=lambda box: -box[4])[:MAX_CANDIDATES]


def crop_square(width, height, box):
    """The square around the box that Ember sees, as (left, top, right, bottom) pixels of the photo."""
    x1, y1, x2, y2 = box[:4]
    side = max(CROP_SCALE * max(x2 - x1, y2 - y1), MIN_CROP)
    side = min(side, width, height)
    left = min(max((x1 + x2) / 2 - side / 2, 0), width - side)
    top = min(max((y1 + y2) / 2 - side / 2, 0), height - side)
    return round(left), round(top), round(left + side), round(top + side)


def crop_jpeg(image, box):
    """The crop Ember sees, as JPEG bytes."""
    buffer = io.BytesIO()
    region = image.crop(crop_square(image.width, image.height, box))
    region.resize((CROP_PIXELS, CROP_PIXELS), Image.Resampling.LANCZOS).save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def crop(image, box):
    return "data:image/jpeg;base64," + base64.b64encode(crop_jpeg(image, box)).decode()


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
