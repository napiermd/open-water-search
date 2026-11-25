"""Verify the published 120-second flight through the normal detector-check command at $0."""
import argparse
import base64
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from threading import Lock

from PIL import Image

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
sys.path.insert(0, str(ROOT / "probe"))
import flag_check  # noqa: E402
import open_water_search  # noqa: E402
from build_pages import live_check  # noqa: E402
from simulated_ember import refuse_network  # noqa: E402

BOXES_SHA256 = "f3197a081cdc8245efbecb48d6dae48981a25c06b2b87802b4e2996852a74104"
# The live log saved replies only. Freeze the request digests reconstructed from the published frames and boxes.
REQUESTS_SHA256 = "0050a9dc1ab48ec65677576818597e98c69f7eab438d7a35ca5ab099dbf4bb8f"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def sealed_bytes(path, expected):
    content = path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == expected, f"{path.name} SHA-256 does not match")
    return content


def request_digest(body):
    return hashlib.sha256(json.dumps(body).encode()).hexdigest()


class SavedEmber:
    limits = None

    def __init__(self, pending):
        self.pending = pending
        self.lock = Lock()

    def count(self, body):
        with self.lock:
            return self.pending[request_digest(body)]["usage"]["input_tokens"]

    def generate(self, body):
        with self.lock:
            return self.pending.pop(request_digest(body))["answer"]["response"]


def prepare_requests(frames, manifest, photos):
    require([f["name"] for f in frames] == [f["frame"] for f in manifest] == [p["frame"] for p in photos],
            "Extracted frame names do not match the published flight")
    digests, crops = {}, {}
    for frame, expected, photo in zip(frames, manifest, photos, strict=True):
        sealed_bytes(frame["path"], expected["sha256"])
        boxes = flag_check.candidates(photo)
        if not boxes:
            continue
        name = frame["name"]
        with Image.open(frame["path"]) as image:
            body = flag_check.request_body(image.convert("RGB"), boxes)
        digests[name] = request_digest(body)
        images = (part for part in body["input"][0]["content"] if part["type"] == "input_image")
        for number, part in enumerate(images, 1):
            crops[f"crops/{name}-flag{number}.jpg"] = base64.b64decode(part["image_url"].split(",", 1)[1])
    require(request_digest(dict(sorted(digests.items()))) == REQUESTS_SHA256, "Reconstructed requests do not match")
    return digests, crops


def verify_outputs(out, saved, crops):
    for filename in ("queue.json", "coverage.json", "detector-boxes.json"):
        require((out / filename).read_bytes() == (RUN / filename).read_bytes(), f"{filename} differs from the published run")
    record = json.loads((out / "search-record.json").read_text())
    for key in ("ending", "coverage_timeline", "sightings", "possible_people", "spent_nanodollars"):
        require(record[key] == saved[key], f"Search record {key} differs from the sealed run")

    coverage = record["coverage_timeline"]
    report = (out / "report.html").read_text()
    links = set(re.findall(r'<a href="#([^"]+)">(?:<span class="photo">)?<img src="([^"]+)"', report))
    targets = set(re.findall(r'<section id="([^"]+)">', report))
    require(targets == {frame["frame"] for frame in coverage}, "Report coverage sections differ")
    require(links == {(frame["frame"], flag["crop"]) for frame in coverage for flag in frame["flags"]},
            "Report crop links do not point to their source sections")
    for path, jpeg in crops.items():
        require((out / path).read_bytes() == jpeg, f"{path} differs from the request crop")

    web = json.loads((ROOT / "pages/runs/live-detector-check.json").read_text())
    expected_web = live_check()
    require(web["timeline"] == expected_web["timeline"], "Web replay timeline differs from sealed coverage")
    seconds = {frame["frame"]: frame["second"] for frame in coverage}
    verdicts = Counter((seconds[item["frame"]], item["text"])
                       for item in record["decision_log"] if item["frame"] is not None)
    web_verdicts = Counter((item["second"], item["line"]) for item in web["printed"] if "second" in item)
    require(verdicts == web_verdicts, "Web replay verdicts or source seconds differ")
    require(web["people"] == expected_web["people"], "Web replay handoffs or metadata differ")


def replay(clip, out):
    clip_manifest = json.loads((ROOT / "mobdrone/clip/scoring-only/manifest.json").read_text())
    with clip.open("rb") as source:
        require(hashlib.file_digest(source, "sha256").hexdigest() == clip_manifest["clip"]["sha256"],
                "clip SHA-256 does not match the published flight")
    manifest_path = ROOT / "runs/prompt-revision/tune/clip/inputs/manifest.json"
    manifest = json.loads(manifest_path.read_text())["frames"]
    photos = json.loads(sealed_bytes(RUN / "detector-boxes.json", BOXES_SHA256))
    seal = json.loads((RUN / "seal.json").read_text())
    saved = json.loads(sealed_bytes(RUN / "search-record-redacted.json", seal["search_record_redacted_sha256"]))
    calls = [json.loads(line) for line in sealed_bytes(RUN / "calls-redacted.jsonl",
                                                       seal["calls_redacted_sha256"]).splitlines()]
    pending, crops = {}, {}

    def sealed_detector(frames):
        digests, request_crops = prepare_requests(frames, manifest, photos)
        require({call["frame"] for call in calls} == digests.keys() and len(calls) == len(digests) == seal["calls"],
                "Saved replies do not cover each flagged frame exactly once")
        pending.update((digests[call["frame"]], call) for call in calls)
        require(len(pending) == len(calls), "Two flagged frames have the same request digest")
        crops.update(request_crops)
        return photos

    with refuse_network():
        open_water_search.main([str(clip), "--mode", "detector-check", "--out", str(out), "--budget", "0.05"],
                               api=SavedEmber(pending), detect=sealed_detector)
    require(not pending, "The search did not consume every saved reply")
    verify_outputs(out, saved, crops)
    print(f"Verified {len(calls)} saved replies and {len(crops)} crop links. Replay: 0 external model calls, $0 spent.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", type=Path, help="the published 120-second MOBDrone clip")
    parser.add_argument("out", type=Path, help="new folder for the generated report and evidence")
    args = parser.parse_args()
    replay(args.clip, args.out)
