"""Offline test harness: fixture flights, a simulated Muse Ember, and the real command run against it.

    flight = write_flight(folder, [(300, 200), (300, 200)])
    ember = SimulatedEmber({("frame-01", -1): '{"tiles":[4,0]}', ("frame-01", 4): '{"points":[[0.5,0.5,0.9]]}'})
    status, printed = run_command([str(flight), "--out", str(out)], ember)

Fixture frames paint each tile of the 3 x 3 grid a flat colour that encodes the frame's place in the flight and
the tile's number. The simulated Ember reads that colour back from the image it receives, so it knows which
frame and tile every request shows, whatever order the requests arrive in. Nothing here opens a network
connection, and run_command fails any test that tries.
"""
import base64
import io
import socket
from contextlib import contextmanager, redirect_stdout

from PIL import Image

import open_water_search
from runner import rectangle

# Colour steps survive JPEG compression and resizing of flat tiles. Red and blue hold the frame index, green the tile.
FRAME_STEP = 8
TILE_STEP = 24
FRAMES_PER_BLUE_STEP = 32
INPUT_TOKENS = 700


def frame_name(index):
    return f"frame-{index + 1:02}"


def write_flight(folder, sizes):
    """Write one JPEG per (width, height) in flight order, named frame-01, frame-02, ... Returns the folder."""
    folder.mkdir(parents=True)
    for index, (width, height) in enumerate(sizes):
        image = Image.new("RGB", (width, height))
        for tile in range(9):
            colour = (FRAME_STEP * (index % FRAMES_PER_BLUE_STEP), TILE_STEP * tile,
                      FRAME_STEP * (index // FRAMES_PER_BLUE_STEP))
            image.paste(colour, rectangle(width, height, tile))
        image.save(folder / f"{frame_name(index)}.jpg", quality=95)
    return folder


def identify(image):
    """Return (frame name, tile) for a close look, or (frame name, -1) for an overview of a fixture frame."""
    width, height = image.size

    def colour_at(x, y):
        red, green, blue = image.getpixel((int(x), int(y)))
        index = round(red / FRAME_STEP) + FRAMES_PER_BLUE_STEP * round(blue / FRAME_STEP)
        return index, round(green / TILE_STEP)

    index, centre_tile = colour_at(width / 2, height / 2)
    _, corner_tile = colour_at(width / 6, height / 6)
    # A close look shows one flat tile. An overview shows the whole grid, so its corner and centre differ.
    return frame_name(index), -1 if corner_tile != centre_tile else centre_tile


def answer(text, input_tokens=INPUT_TOKENS, output_tokens=100):
    """A completed Ember reply whose answer is text."""
    return {"status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": input_tokens, "input_tokens_details": {"cached_tokens": 0},
                      "output_tokens": output_tokens}}


class SimulatedEmber:
    """Stands in for runner.Meta.

    replies maps (frame name, tile) to what Ember returns for that request, with tile -1 for the overview:
    answer text, a full reply such as one recorded from a paid run, or an exception to raise instead of
    replying. A request with no scripted reply raises KeyError, which the command treats as a failed request.
    requests holds the body of every request sent for an answer, in order.
    """

    def __init__(self, replies):
        self.replies = replies
        self.requests = []

    def reply_to(self, body):
        content = body["input"][0]["content"]
        url = next(part["image_url"] for part in content if part["type"] == "input_image")
        with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as image:
            reply = self.replies[identify(image.convert("RGB"))]
        return answer(reply) if isinstance(reply, str) else reply

    def count(self, body):
        reply = self.reply_to(body)
        return INPUT_TOKENS if isinstance(reply, Exception) else reply["usage"]["input_tokens"]

    def generate(self, body):
        self.requests.append(body)
        reply = self.reply_to(body)
        if isinstance(reply, Exception):
            raise reply
        return reply


@contextmanager
def refuse_network():
    def refuse(*args, **kwargs):
        raise AssertionError("an offline test tried to open a network connection")

    connect = socket.socket.connect
    socket.socket.connect = refuse
    try:
        yield
    finally:
        socket.socket.connect = connect


def run_command(arguments, ember):
    """Run the real command with ember in place of Meta. Returns its exit status and what it printed."""
    printed = io.StringIO()
    status = 0
    with redirect_stdout(printed), refuse_network():
        try:
            open_water_search.main(arguments, ember)
        except SystemExit as exit:
            status = 0 if exit.code is None else exit.code
    return status, printed.getvalue()
