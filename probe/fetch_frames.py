"""Download the 60 frames and their labels from the pinned SeaDronesSee mirror and check every hash.

    python fetch_frames.py

Writes inputs/images and scoring-only/labels for the November 23 run, and the same folders under
validation/. Files already present with the right hash are skipped.
"""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIRROR = "https://huggingface.co/datasets/dronefreak/SeaDronesSee/resolve/deb1f872ffe7efa4b7ee3a672562d16b6dc0ca5c/data"
SETS = {ROOT: "train", ROOT / "validation": "val"}


def fetch(url, path, sha256):
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256:
        return
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise SystemExit(f"Hash mismatch for {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    for base, split in SETS.items():
        frames = json.loads((base / "inputs/manifest.json").read_text())["frames"]
        labels = {row["frame"]: row for row in json.loads((base / "scoring-only/manifest.json").read_text())["frames"]}
        for frame in frames:
            source = Path(frame["source"])
            fetch(f"{MIRROR}/images/{split}/{source}", base / "inputs" / frame["image"], frame["sha256"])
            label = labels[frame["frame"]]
            fetch(f"{MIRROR}/labels/{split}/{source.with_suffix('.txt')}", base / "scoring-only" / label["label"], label["sha256"])
        print(f"{base.relative_to(ROOT) if base != ROOT else 'run'}: {len(frames)} frames and labels verified")


if __name__ == "__main__":
    main()
