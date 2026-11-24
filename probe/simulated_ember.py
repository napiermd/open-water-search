"""Offline test harness: fixture flights, a simulated Muse Ember, and the real command run against it.

    flight = write_flight(folder, [(300, 200), (300, 200)])
    ember = SimulatedEmber({("frame-01", -1): '{"tiles":[4,0]}', ("frame-01", 4): '{"points":[[0.5,0.5,0.9]]}'})
    status, printed = run_command([str(flight), "--out", str(out)], ember)

In agent mode Ember answers with tool calls instead, scripted turn by turn for each frame:

    ember = SimulatedEmber({}, conversations={"frame-01": [[("look_closer", {"tile": 4})], [("move_to_next_frame", {})]]})

Fixture frames paint each tile of the 3 x 3 grid a flat colour that encodes the frame's place in the flight and
the tile's number. The simulated Ember reads that colour back from the image it receives, so it knows which
frame and tile every request shows, whatever order the requests arrive in. Nothing here opens a network
connection, and run_command fails any test that tries.
"""
import base64
import copy
import io
import json
import socket
import threading
import time
from collections import Counter
from contextlib import contextmanager, redirect_stdout

from PIL import Image

import open_water_search
from runner import LIMIT, price, rectangle

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


def tool_calls(call_ids, calls, input_tokens=INPUT_TOKENS, output_tokens=100):
    """A completed Ember reply that makes each (tool name, arguments) call in calls, in order."""
    return {"status": "completed",
            "output": [{"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(arguments)}
                       for call_id, (name, arguments) in zip(call_ids, calls)],
            "usage": {"input_tokens": input_tokens, "input_tokens_details": {"cached_tokens": 0},
                      "output_tokens": output_tokens}}


def images_in(body):
    """(frame name, tile) of every image in a request body, in order, with tile -1 for an overview."""
    images = []
    for item in body["input"]:
        for part in item.get("content", []):
            if part["type"] == "input_image":
                with Image.open(io.BytesIO(base64.b64decode(part["image_url"].split(",", 1)[1]))) as image:
                    images.append(identify(image.convert("RGB")))
    return images


class SimulatedEmber:
    """Stands in for runner.Meta.

    replies maps (frame name, tile) to what Ember returns for that request, with tile -1 for the overview:
    answer text, a full reply such as one recorded from a paid run, or an exception to raise instead of
    replying. A list scripts successive tries of the same request, such as a 429 and then an answer; the
    last entry repeats. A request with no scripted reply raises KeyError, which the command treats as a
    failed request.

    conversations scripts agent mode, where each request carries tools and one frame's conversation so far. It maps
    frame name to Ember's successive replies to that frame's requests. A reply is a list of (tool name, arguments)
    calls, a full reply, or an exception such as a 429. A request past the end of a frame's script raises
    IndexError, which the command treats as a failed request. A request that leaves one of Ember's earlier tool
    calls without its output fails the same way, as Meta refuses it.

    latency maps (frame name, tile) to the seconds Ember takes to answer that request; others answer at once.
    limits stands for Meta's rate-limit headers, as open_water_search.Ember reads them.

    While it runs it notes every request sent, with when it was sent, the most requests in flight at once,
    and the most ever committed: what was paid so far plus the worst-case cost of every request in flight.
    requests holds the body of every request sent for an answer, in the order they were sent.
    """

    def __init__(self, replies, latency=None, limits=None, conversations=None):
        self.replies = replies
        self.latency = latency or {}
        self.limits = limits
        self.conversations = conversations or {}
        self.turns_taken = Counter()
        self.lock = threading.Lock()
        self.sent = []
        self.in_flight = []
        self.paid = 0
        self.most_in_flight = 0
        self.most_committed = 0
        self.requests = []

    def request_in(self, body):
        """(frame name, tile) of the request's first image. In agent mode that is the frame's overview."""
        return images_in(body)[0]

    def reply_to(self, body, take=False):
        request = self.request_in(body)
        if "tools" in body:
            return self.next_turn(request[0], body, take)
        reply = self.replies[request]
        if isinstance(reply, list):
            reply = reply.pop(0) if take and len(reply) > 1 else reply[0]
        return answer(reply) if isinstance(reply, str) else reply

    def next_turn(self, frame, body, take):
        called = {item["call_id"] for item in body["input"] if item.get("type") == "function_call"}
        answered = {item["call_id"] for item in body["input"] if item.get("type") == "function_call_output"}
        if called != answered:
            raise ValueError("a tool call has no output")
        turn = self.turns_taken[frame]
        reply = self.conversations[frame][turn]
        if take:
            self.turns_taken[frame] += 1
        if isinstance(reply, list):
            return tool_calls([f"{frame}-turn{turn}-call{n}" for n in range(len(reply))], reply)
        return reply

    def count(self, body):
        reply = self.reply_to(body)
        return INPUT_TOKENS if isinstance(reply, Exception) else reply["usage"]["input_tokens"]

    def generate(self, body):
        request = self.request_in(body)
        worst = price(self.count(body), 0, LIMIT)
        with self.lock:
            reply = self.reply_to(body, take=True)
            self.sent.append((time.monotonic(), request))
            # Keep the body as sent: the command goes on adding to a conversation after sending it.
            self.requests.append(copy.deepcopy(body))
            self.in_flight.append(worst)
            self.most_in_flight = max(self.most_in_flight, len(self.in_flight))
            self.most_committed = max(self.most_committed, self.paid + sum(self.in_flight))
        time.sleep(self.latency.get(request, 0))
        with self.lock:
            self.in_flight.remove(worst)
            if not isinstance(reply, Exception):
                usage = reply["usage"]
                self.paid += price(usage["input_tokens"], usage["input_tokens_details"]["cached_tokens"],
                                   usage["output_tokens"])
        if isinstance(reply, Exception):
            raise reply
        return reply

    def times_sent(self, request):
        return [when for when, sent in self.sent if sent == request]


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


def run_command(arguments, ember, as_given=False):
    """Run the real command with ember in place of Meta. Returns its exit status and what it printed.

    Scripted answers are written in the frozen prompts' fractions, so the command runs with --format frozen unless
    a test names a format itself or passes as_given=True to run the arguments exactly as written.
    """
    if not as_given and "--format" not in arguments:
        arguments = [*arguments, "--format", "frozen"]
    printed = io.StringIO()
    status = 0
    with redirect_stdout(printed), refuse_network():
        try:
            open_water_search.main(arguments, ember)
        except SystemExit as exit:
            status = 0 if exit.code is None else exit.code
    return status, printed.getvalue()
