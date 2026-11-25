"""Paid harder pilot. Run with --key-file ~/.config/open-water-search/meta.key.

One ledger per pilot, in this directory. A flag's output index i is zero-based.
Only the operator launches the live CLI. Tests inject a simulated Ember client.
"""
import argparse
import base64
import copy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "probe"))
import flag_check as fc
from open_water_search import Ember, RateLimited
from runner import MODEL, price

PILOT_SHA = "6b584a523df6c298a38bb8fa147aaeedffcc58d974eb3e8cd51d4239c305fe22"
CAP = 150_000_000
IMAGES = ROOT.parents[1] / "data/mobdrone-seconds"
PAD_PROMPT = (fc.PROMPT + " Answer person=true for a person in the water at the centre. "
              "Answer nearby=true only if there is a person in the water elsewhere in the crop "
              "and none at the centre. If neither is visible, set both false.")
THREE_PROMPT = ("These three crops show the same flagged coordinates one second before, at the flag, "
                "and one second after. Use the neighbours as context. Return one verdict (crop 1): "
                "is a person in the water at the centre of the MIDDLE image? Give confidence from 0 to 1 "
                "and a few words about what is there.")
PAD_FORMAT = copy.deepcopy(fc.CHECKS)
pad_item = PAD_FORMAT["schema"]["properties"]["crops"]["items"]
pad_item["required"].append("nearby")
pad_item["properties"]["nearby"] = {"type": "boolean"}


def photo(row, images):
    path = images / Path(row["video"]).stem / f"second-{row['second']:05d}.jpg"
    data = path.read_bytes()
    if row.get("sha256") and hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError(f"Changed pilot JPEG: {path}")
    with Image.open(io.BytesIO(data)) as source:
        if source.size != (row["width"], row["height"]):
            raise ValueError(f"Wrong dimensions: {path}")
        return source.convert("RGB")


def padded(image, box):
    x1, y1, x2, y2 = box[:4]
    side = min(image.width, image.height, max(fc.MIN_CROP, fc.CROP_SCALE * max(x2-x1, y2-y1)))
    cx, cy = (x1+x2)/2, (y1+y2)/2
    # PIL fills out-of-frame pixels black. Never slide the window inward.
    rect = tuple(round(v) for v in (cx-side/2, cy-side/2, cx+side/2, cy+side/2))
    crop = image.crop(rect).resize((fc.CROP_PIXELS, fc.CROP_PIXELS), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    crop.save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def request(arm, rows, i, images):
    middle = rows[len(rows)//2]
    image = photo(middle, images)
    if arm == "current":
        return fc.request_body(image, middle["flags"])
    three = arm == "three"
    body = fc.request_body(image, [], THREE_PROMPT if three else PAD_PROMPT)
    content = body["input"][0]["content"]
    if three:
        box = middle["flags"][i]
        pictures = [(label, padded(image if row is middle else photo(row, images), box))
                    for label, row in zip(("Previous second", "Middle second", "Next second"), rows)]
    else:
        body["text"]["format"] = PAD_FORMAT
        pictures = [(f"Crop {n}", padded(image, box)) for n, box in enumerate(middle["flags"], 1)]
    for label, url in pictures:
        content.extend([{"type": "input_text", "text": label + ":"}, {"type": "input_image", "image_url": url}])
    return body


def verdicts(reply, arm, frame, indices):
    if reply.get("status") != "completed":
        raise ValueError("Incomplete response")
    raw = "".join(part["text"] for item in reply["output"] for part in item.get("content", [])
                  if part["type"] == "output_text")
    crops = json.loads(raw)["crops"]
    if not isinstance(crops, list) or len(crops) != len(indices):
        raise ValueError("Wrong number of verdicts")
    results = {}
    for crop in crops:
        n, yes = crop["crop"], crop["person"]
        nearby = crop["nearby"] if arm == "padded" else False
        confidence = crop["confidence"]
        if (type(n) is not int or not 1 <= n <= len(indices) or n in results or
                type(yes) is not bool or type(nearby) is not bool or (yes and nearby) or
                type(confidence) not in (int, float) or not 0 <= confidence <= 1 or
                not isinstance(crop["what"], str)):
            raise ValueError("Invalid crop verdict")
        results[n] = dict(arm=arm, frame=frame, i=indices[n-1], yes=yes, nearby=nearby,
                          confidence=confidence, what=crop["what"])
    return [results[n] for n in sorted(results)]


class Stopped(RuntimeError):
    pass


class Ledger:
    """Every access is under gate. The directory lock excludes a second process."""

    def __init__(self, folder, manifest):
        self.gate = threading.Condition()
        self.db = sqlite3.connect(folder / "ledger.sqlite", check_same_thread=False)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, manifest TEXT, stop TEXT);
            CREATE TABLE IF NOT EXISTS retries (
                arm TEXT, frame TEXT, i INTEGER, phase TEXT, PRIMARY KEY (arm, frame, i));
            CREATE TABLE IF NOT EXISTS calls (
                arm TEXT, frame TEXT, i INTEGER, reserved INTEGER NOT NULL, paid INTEGER,
                result TEXT, PRIMARY KEY (arm, frame, i));
        """)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO settings VALUES (1, ?, NULL)", (manifest,))
        signature, self.stop = self.db.execute("SELECT manifest,stop FROM settings WHERE id=1").fetchone()
        if signature != manifest:
            raise Stopped("Pilot manifest changed")
        self.resume_at = 0.0
        self.active = 0
        self.known = set()
        self.dismissed = []
        self.log = folder / "verdicts.jsonl"
        # SQLite commits first. Rebuild the derived log even after a torn JSONL write.
        tmp = self.log.with_suffix(".jsonl.tmp")
        with tmp.open("w") as stream:
            for arm, frame, i, paid, result in self.db.execute(
                    "SELECT arm,frame,i,paid,result FROM calls ORDER BY rowid"):
                self.known.add((arm, frame, i))
                if paid is None:
                    self.latch("Unresolved generation reservation; reconcile charge")
                elif result is None:
                    continue
                else:
                    rows = json.loads(result)
                    self.remember(rows)
                    for row in rows:
                        stream.write(json.dumps(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        tmp.replace(self.log)
        # Reconstruct the consecutive-failure streak in completion order, independently of dispatch order.
        self.db.execute("CREATE TABLE IF NOT EXISTS streak (id INTEGER PRIMARY KEY, failures INTEGER)")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO streak VALUES (1,0)")
        self.failures = self.db.execute("SELECT failures FROM streak").fetchone()[0]

    def remember(self, rows):
        self.dismissed.extend((r["frame"], r["i"]) for r in rows
                              if r["arm"] == "padded" and not r["yes"] and not r["nearby"])

    def latch(self, reason):
        self.stop = self.stop or reason
        with self.db:
            self.db.execute("UPDATE settings SET stop=? WHERE id=1", (self.stop,))

    def provider_call(self, key, phase, method, body):
        while True:
            with self.gate:
                while not self.stop and (delay := self.resume_at - time.monotonic()) > 0:
                    self.gate.wait(delay)
                if self.stop:
                    raise Stopped(self.stop)
            try:
                return method(body)
            except RateLimited as error:
                # Ember raises this only for an explicit HTTP 429. A rejected generation
                # has no output or charge. Its durable reservation covers the one retry.
                # Transport loss is never eligible for this branch.
                cause = error.__cause__
                detail = cause.read(8192).lower() if hasattr(cause, "read") else b""
                with self.gate:
                    if any(word in detail for word in (b"insufficient_quota", b"billing", b"credit balance",
                                                       b"payment required", b"quota exhausted")):
                        self.latch("Provider billing or quota breaker")
                    elif self.db.execute("SELECT 1 FROM retries WHERE arm=? AND frame=? AND i=?", key).fetchone():
                        self.latch("Persistent HTTP 429; retry exhausted")
                    else:
                        with self.db:
                            self.db.execute("INSERT INTO retries VALUES (?,?,?,?)", (*key, phase))
                        delay = min(60, max(1, error.retry_after or 1))
                        self.resume_at = max(self.resume_at, time.monotonic() + delay)
                    self.gate.notify_all()
                    if self.stop:
                        raise Stopped(self.stop) from None

    def reserve(self, key, worst):
        with self.gate:
            while not self.stop:
                total, = self.db.execute("SELECT COALESCE(SUM(COALESCE(paid,reserved)),0) FROM calls").fetchone()
                if total + worst <= CAP:
                    with self.db:
                        self.db.execute("INSERT INTO calls VALUES (?,?,?,?,NULL,NULL)", (*key, worst))
                    self.active += 1
                    return True
                if not self.active:
                    self.latch("Spending cap reached")
                    break
                self.gate.wait()
            return False

    def finish(self, key, paid, rows):
        with self.gate:
            self.failures = 0 if rows is not None else self.failures + 1
            with self.db:
                self.db.execute("UPDATE calls SET paid=?,result=? WHERE arm=? AND frame=? AND i=?",
                                (paid, json.dumps(rows) if rows is not None else None, *key))
                self.db.execute("UPDATE streak SET failures=?", (self.failures,))
                if self.failures >= 10:
                    self.stop = self.stop or "Ten consecutive unusable replies"
                    self.db.execute("UPDATE settings SET stop=?", (self.stop,))
            if rows is not None:
                with self.log.open("a") as stream:
                    for row in rows:
                        stream.write(json.dumps(row) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                self.remember(rows)
            self.active -= 1
            self.gate.notify_all()


def run(pilot, images, folder, workers, api_factory):
    if not 1 <= workers <= 8:
        raise ValueError("Use 1 to 8 workers")
    raw = pilot.read_bytes()
    frames = json.loads(raw)
    by_name = {r["frame"]: r for r in frames}
    by_time = {(r["video"], r["block"], r["second"]): r for r in frames}
    if len(by_name) != len(frames) or len(by_time) != len(frames):
        raise ValueError("Duplicate pilot frame")
    directory = os.open(folder, os.O_RDONLY)
    try:
        fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = Ledger(folder, hashlib.sha256(raw).hexdigest())
        try:
            run_stages(ledger, frames, by_name, by_time, images, workers, api_factory)
        finally:
            ledger.db.close()
    finally:
        os.close(directory)


def run_stages(ledger, frames, by_name, by_time, images, workers, api_factory):
    clients = threading.local()

    def check(job):
        arm, rows, i = job
        middle = rows[len(rows)//2]
        key = arm, middle["frame"], i
        with ledger.gate:
            if ledger.stop or key in ledger.known:
                return
        try:
            body = request(arm, rows, i, images)
            if not hasattr(clients, "api"):
                clients.api = api_factory()
            # Ember.count sends the exact input (including every actual JPEG) to Meta's
            # input-token counter. It omits the schema; bound omitted fields by UTF-8
            # bytes plus framing. Bill all counted tokens uncached and all output tokens.
            extra = {k: v for k, v in body.items() if k not in ("input", "model")}
            with ledger.gate:
                if ledger.stop:
                    return
            counted = ledger.provider_call(key, "count", clients.api.count, body)
            bound = counted + len(json.dumps(extra).encode()) + 256
            worst = price(bound, 0, body["max_output_tokens"])
            if not ledger.reserve(key, worst):
                return
            reply = ledger.provider_call(key, "generate", clients.api.generate, body)
            usage = reply["usage"]
            paid = price(usage["input_tokens"], usage.get("input_tokens_details", {}).get("cached_tokens", 0),
                         usage["output_tokens"])
            if (usage["input_tokens"] > bound or usage["output_tokens"] > body["max_output_tokens"]
                    or paid > worst):
                raise ValueError("Usage exceeds reservation")
            if reply.get("error") or reply.get("status") == "failed":
                raise RuntimeError("Provider reported a failure")
            indices = [i] if arm == "three" else range(len(middle["flags"]))
            try:
                records = verdicts(reply, arm, middle["frame"], indices)
            except (ValueError, KeyError, TypeError, AttributeError):
                records = None
            ledger.finish(key, paid, records)
        except BaseException as error:
            # Includes billing, quota, rate limits, timeouts and unknown usage. Keep
            # any outstanding reservation at full value, including after process loss.
            with ledger.gate:
                try:
                    ledger.latch(f"{arm} {middle['frame']}: {type(error).__name__}; review before resuming")
                finally:
                    ledger.gate.notify_all()
            raise

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for arm in ("current", "padded", "three"):
            if ledger.stop:
                break
            if arm == "three":
                jobs = []
                for frame, i in ledger.dismissed:
                    row = by_name[frame]
                    rows = [by_time.get((row["video"], row["block"], row["second"]+d)) for d in (-1, 0, 1)]
                    if all(rows):
                        jobs.append((arm, rows, i))
            else:
                jobs = [(arm, [row], -1) for row in frames if row["flags"]]
            # Stage barrier: every padded completion is durable before selecting follow-ups.
            for _ in pool.map(check, jobs):
                pass
    if ledger.stop:
        raise Stopped(ledger.stop)
    failed, = ledger.db.execute("SELECT COUNT(*) FROM calls WHERE result IS NULL").fetchone()
    if failed:
        raise Stopped(f"{failed} billed calls returned unusable verdicts")
    calls, paid = ledger.db.execute("SELECT COUNT(*), COALESCE(SUM(paid),0) FROM calls").fetchone()
    print(f"{MODEL} via Meta Responses: {calls} completed calls, {paid} nanodollars")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, help="Otherwise use MODEL_API_KEY")
    parser.add_argument("--parallel", type=int, choices=range(1, 9), default=8)
    args = parser.parse_args()
    pilot = HERE / "pilot.json"
    if hashlib.sha256(pilot.read_bytes()).hexdigest() != PILOT_SHA:
        raise SystemExit("Manifest differs from the approved seven-clip pilot")
    if args.key_file:
        os.environ["MODEL_API_KEY"] = args.key_file.expanduser().read_text().strip()
    try:
        run(pilot, IMAGES, HERE, args.parallel, Ember)
    except (Stopped, BlockingIOError) as error:
        raise SystemExit(str(error))


if __name__ == "__main__":
    main()
