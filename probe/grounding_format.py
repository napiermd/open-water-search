"""Meta's grounding format for close looks: each mark is a point on a 0-1,000 grid over the image Ember received.

Structured output on the Responses API (text.format with a JSON schema) forces every answer into the MARKS shape.
The command asks for close-look marks in this format by default. --format frozen keeps the published prompts in
runner.py.
"""
import json
import math

GRID = 1000
INSPECT = ("Mark each person swimming or floating in the water. Give each mark as a point on a 0 to 1,000 grid over "
           "this image, with (0,0) at the top left, x across and y down, and a confidence from 0 to 1. "
           "Return an empty list of points if there are none.")
MARKS = {"type": "json_schema", "name": "marks", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["points"],
    "properties": {"points": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["x", "y", "confidence"],
        "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "confidence": {"type": "number"}}}}}}}


def to_frame(value, start, end):
    """Clamp a grid value into 0-1,000, then convert it to a frame pixel from start up to, but not on, end."""
    share = min(max(value, 0), GRID) / GRID
    return start + min(share * (end - start), math.nextafter(float(end), 0) - start)


def read_marks(event):
    """Add the answer's points, in original-frame pixels, to event, or mark the answer unusable.

    event["rect"] is the part of the frame Ember was shown: the whole frame for an overview, one tile for a
    close look. The image Ember received is that rectangle resized to scale, so a grid point maps straight back
    through the rectangle, whatever the resize.
    """
    reply = event["response"]
    try:
        if reply.get("status") != "completed":
            raise ValueError("incomplete response")
        raw = "".join(c["text"] for item in reply["output"] for c in item.get("content", []) if c["type"] == "output_text")
        left, top, right, bottom = event["rect"]
        points = []
        for mark in json.loads(raw)["points"]:
            x, y, confidence = mark["x"], mark["y"], mark["confidence"]
            if not all(type(n) in (int, float) for n in (x, y, confidence)) or not 0 <= confidence <= 1:
                raise ValueError("invalid mark")
            points.append([to_frame(x, left, right), to_frame(y, top, bottom), confidence])
        event["points"] = points
    except (ValueError, TypeError, KeyError):
        event["failure"] = "unusable response"
    return event
