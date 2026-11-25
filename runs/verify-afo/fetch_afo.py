"""Download the 300 AFO photos in runs/verify-afo/frames.json and their labels, and list them in the repo's layouts.

    python runs/verify-afo/fetch_afo.py SAMPLE_DIR

Each photo is fetched from whichever of the release's three parts holds it, and its six-class label file from PART_1.
SAMPLE_DIR/images gets the photos and SAMPLE_DIR/labels one YOLO file per photo holding only its `human` boxes (class
0), the class scored as a person. Boxes of other classes are left out, so a mark on a board, kayak, buoy or boat
counts as a false alarm. Writes runs/verify-afo/inputs/manifest.json and scoring-only/manifest.json with the SHA-256
of every photo and label file, and links inputs/images and scoring-only/labels to SAMPLE_DIR. Prints no label
statistics. The photos and labels stay out of the repository (CC BY-NC-SA 3.0).
"""
import hashlib
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

RUN = Path(__file__).resolve().parent
BASE = "https://huggingface.co/datasets/jgasienica/afo-dataset/resolve/main"


def get(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def fetch(name, sample):
    for part in (1, 2, 3):
        try:
            data = get(f"{BASE}/PART_{part}/PART_{part}/images/{name}")
            break
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
    else:
        raise SystemExit(f"{name} is in none of the three parts")
    (sample / "images" / name).write_bytes(data)
    six = get(f"{BASE}/PART_1/PART_1/6categories/{Path(name).stem}.txt").decode()
    humans = "".join(line + "\n" for line in six.splitlines() if line.split() and line.split()[0] == "0")
    (sample / "labels" / f"{Path(name).stem}.txt").write_text(humans)
    return part


def link(path, target):
    if path.is_symlink():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target.resolve(), target_is_directory=True)


def main(sample):
    listing = json.loads((RUN / "frames.json").read_text())
    names = [frame["image"] for frame in listing["frames"]]
    (sample / "images").mkdir(parents=True, exist_ok=True)
    (sample / "labels").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as pool:
        parts = list(pool.map(lambda name: fetch(name, sample), names))
    inputs, scoring = [], []
    for name, part in sorted(zip(names, parts)):
        stem = Path(name).stem
        with Image.open(sample / "images" / name) as image:
            width, height = image.size
        inputs.append(dict(frame=stem, image=f"images/{name}", part=part, width=width, height=height,
                           sha256=hashlib.sha256((sample / "images" / name).read_bytes()).hexdigest()))
        scoring.append(dict(frame=stem, label=f"labels/{stem}.txt",
                            sha256=hashlib.sha256((sample / "labels" / f"{stem}.txt").read_bytes()).hexdigest()))
    (RUN / "inputs").mkdir(exist_ok=True)
    (RUN / "scoring-only").mkdir(exist_ok=True)
    (RUN / "inputs" / "manifest.json").write_text(json.dumps(dict(
        dataset=listing["dataset"], source=listing["source"], license=listing["license"], list="runs/verify-afo/frames.json",
        list_sha256=hashlib.sha256((RUN / "frames.json").read_bytes()).hexdigest(), frames=inputs), indent=2) + "\n")
    (RUN / "scoring-only" / "manifest.json").write_text(json.dumps(dict(
        format="YOLO normalized xywh, class 0 = person (AFO's human class only; other classes left out)",
        labels="PART_1/PART_1/6categories", frames=scoring), indent=2) + "\n")
    link(RUN / "inputs" / "images", sample / "images")
    link(RUN / "scoring-only" / "labels", sample / "labels")
    print(f"fetched {len(inputs)} photos and their labels into {sample}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
