"""Run open_water_search.py --mode detector-check on the 300 new MOBDrone frames, with Ember's sealed answers replayed.

    python runs/verify-mobdrone/replay_one_command.py OUT DETECTOR_PYTHON

OUT is a new folder for the results. DETECTOR_PYTHON has ultralytics installed (see detector/README.md). The frames
come from probe/extract_mobdrone.py with --list runs/verify-mobdrone/frames.json --out runs/verify-mobdrone.

Each request is matched to the sealed run's answer by the SHA-256 of its exact body, so a request that differs in any
byte from the sealed run has no answer and fails. No network, no key, no spend.
On November 24 all 207 requests matched, and the search record scored 210 of 297 found with 38
false alarms, as sealed.
"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, "probe")
import flag_check  # noqa: E402
import open_water_search  # noqa: E402
from simulated_ember import refuse_network  # noqa: E402

images = Path("runs/verify-mobdrone/inputs/images")
answers = {}
for line in open("runs/verify-mobdrone/run/checks-redacted.jsonl"):
    check = json.loads(line)
    with Image.open(images / f"{check['frame']}.jpg") as opened:
        body = flag_check.request_body(opened.convert("RGB"), check["boxes"])
    answers[hashlib.sha256(json.dumps(body).encode()).hexdigest()] = check


class ReplayedEmber:
    limits = None

    def __init__(self):
        self.matched = 0

    def count(self, body):
        return answers[hashlib.sha256(json.dumps(body).encode()).hexdigest()]["usage"]["input_tokens"]

    def generate(self, body):
        check = answers[hashlib.sha256(json.dumps(body).encode()).hexdigest()]
        self.matched += 1
        return check["response"]


ember = ReplayedEmber()
with refuse_network():
    open_water_search.main([str(images), "--out", sys.argv[1], "--mode", "detector-check",
                            "--detector-python", sys.argv[2], "--budget", "0.10"], ember)
print("replayed answers matched:", ember.matched, "of", len(answers))
