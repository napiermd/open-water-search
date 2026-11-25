"""Offline tests. No credential access, token-count requests or generation requests to Meta."""
import base64
from contextlib import ExitStack, closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image

import run_pilot as pilot


def pictures(body):
    return [item["image_url"] for item in body["input"][0]["content"] if item["type"] == "input_image"]


class Fake:
    def __init__(self):
        self.counted = []
        self.generated = []
        self.count_errors = []
        self.generate_errors = []
        self.invalid = False

    def count(self, body):
        self.counted.append(body)
        if self.count_errors:
            raise self.count_errors.pop(0)
        return 100 * len(pictures(body))

    def generate(self, body):
        self.generated.append(body)
        if self.generate_errors:
            raise self.generate_errors.pop(0)
        prompt = body["input"][0]["content"][0]["text"]
        n = 1 if prompt == pilot.THREE_PROMPT else len(pictures(body))
        crops = []
        for i in range(1, n+1):
            row = dict(crop=i, person=i == 1 or prompt == pilot.THREE_PROMPT, confidence=0.9, what="water")
            if prompt == pilot.PAD_PROMPT:
                row["nearby"] = i == 2
            crops.append(row)
        return dict(status="completed", output=[dict(content=[dict(type="output_text",
                    text=json.dumps({"crops": [] if self.invalid else crops[::-1]}))])],
                    usage=dict(input_tokens=100*len(pictures(body)), output_tokens=20))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.images = self.root / "v"
        self.images.mkdir()
        self.api = Fake()
        self.pilot = self.root / "pilot.json"
        self.frames = []
        for n in range(5):
            with Image.new("RGB", (140, 120), (80, 45*n, 60)) as image:
                image.save(self.images / f"second-{n:05d}.jpg")
            self.frames.append(dict(frame=str(n), second=n, video_frame=n*30, video="v.mp4",
                        block="a" if n < 3 else "b", width=140, height=120,
                        flags=[[18, 20, 23, 26, .6], [83, 52, 97, 56, .8], [n+1, 1, n+7, 7, .2]]))

    def execute(self, workers=1):
        self.pilot.write_text(json.dumps(self.frames))
        pilot.run(self.pilot, self.root, self.root, workers, lambda: self.api)

    def rows(self):
        return [json.loads(line) for line in (self.root / "verdicts.jsonl").read_text().splitlines()]

    def test_batches_edges_middle_coordinates_and_restart(self):
        self.execute(4)
        rows = self.rows()
        self.assertEqual(len(rows), 31)
        self.assertEqual([("1", 2, True)], [(r["frame"], r["i"], r["yes"]) for r in rows if r["arm"] == "three"])
        padded = {r["i"]: (r["yes"], r["nearby"]) for r in rows if r["arm"] == "padded" and r["frame"] == "1"}
        self.assertEqual(padded, {0: (True, False), 1: (False, True), 2: (False, False)})
        triple = self.api.generated[-1]
        box = self.frames[1]["flags"][2]
        with ExitStack() as stack:
            expected = [pilot.padded(stack.enter_context(pilot.photo(r, self.root)), box) for r in self.frames[:3]]
        self.assertEqual(pictures(triple), expected)
        with io.BytesIO(base64.b64decode(expected[1].split(",")[1])) as buf, Image.open(buf) as im:
            self.assertEqual(im.size, (224, 224))
            self.assertEqual(im.getpixel((5, 5)), (0, 0, 0))
            self.assertTrue(all(abs(a-b) <= 3 for a, b in zip(im.getpixel((112, 112)), (80, 45, 60))))
        self.assertCountEqual([id(b) for b in self.api.generated], [id(b) for b in self.api.counted])
        (self.root / "verdicts.jsonl").write_text("truncated")
        self.execute()
        self.assertCountEqual(rows, self.rows())
        self.assertEqual(len(self.api.generated), 11)

    def test_first_count_429_recovers(self):
        self.frames = self.frames[:1]
        self.api.count_errors = [pilot.RateLimited(0)]
        self.execute()
        self.assertEqual((len(self.api.counted), len(self.api.generated)), (3, 2))

    def test_generation_429_once_and_only_after_reservation(self):
        self.frames = self.frames[:1]
        self.api.generate_errors = [pilot.RateLimited(0)]
        self.execute()
        self.assertEqual(len(self.api.generated), 3)
        with closing(sqlite3.connect(self.root / "ledger.sqlite")) as db:
            self.assertEqual(db.execute("SELECT phase FROM retries").fetchall(), [("generate",)])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM calls").fetchone(), (2,))

    def test_second_429_persistently_stops_even_across_count_and_generation(self):
        self.api.count_errors = [pilot.RateLimited(None)]
        self.api.generate_errors = [pilot.RateLimited(None)]
        for _ in range(2):
            with self.assertRaisesRegex(pilot.Stopped, "Persistent HTTP 429"):
                self.execute()
        self.assertEqual(len(self.api.generated), 1)

    def test_ambiguous_charge_is_held_on_restart(self):
        self.api.generate_errors = [TimeoutError()]
        with self.assertRaises(TimeoutError):
            self.execute()
        with self.assertRaises(pilot.Stopped):
            self.execute()
        with closing(sqlite3.connect(self.root / "ledger.sqlite")) as db:
            worst, paid = db.execute("SELECT reserved,paid FROM calls").fetchone()
            self.assertGreater(worst, 0)
            self.assertIsNone(paid)
        self.assertEqual(len(self.api.generated), 1)

    def test_crash_after_reservation_blocks_new_dispatch(self):
        self.pilot.write_text(json.dumps(self.frames))
        ledger = pilot.Ledger(self.root, pilot.hashlib.sha256(self.pilot.read_bytes()).hexdigest())
        ledger.reserve(("current", "0", -1), 100)
        ledger.db.close()
        with self.assertRaisesRegex(pilot.Stopped, "Unresolved"):
            self.execute()
        self.assertFalse(self.api.counted)

    def test_ten_invalid_replies_trip_persistent_breaker(self):
        self.api.invalid = True
        for _ in range(2):
            with self.assertRaisesRegex(pilot.Stopped, "Ten consecutive"):
                self.execute()
        self.assertEqual(len(self.api.generated), 10)
        self.assertEqual(self.rows(), [])

    def test_concurrent_workers_reserve_full_bodies_before_dispatch(self):
        generate = self.api.generate
        observed = []
        lock = threading.Lock()
        def inspect(body):
            with closing(sqlite3.connect(self.root / "ledger.sqlite")) as db:
                total, = db.execute("SELECT SUM(COALESCE(paid,reserved)) FROM calls").fetchone()
                counted = 100*len(pictures(body))
                text_bytes = len(json.dumps({k:v for k,v in body.items() if k not in ("model","input")}).encode())
                minimum = pilot.price(counted + text_bytes, 0, body["max_output_tokens"])
                with lock:
                    observed.append((total, minimum))
            time.sleep(.01)
            return generate(body)
        self.api.generate = inspect
        with patch.object(pilot, "CAP", 1_250_000):
            with self.assertRaisesRegex(pilot.Stopped, "cap"):
                self.execute(8)
        self.assertTrue(observed)
        self.assertTrue(all(minimum <= total <= 1_250_000 for total, minimum in observed))
        self.assertLess(len(observed), 11)


if __name__ == "__main__":
    unittest.main()
