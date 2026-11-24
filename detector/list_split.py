"""List the SeaDronesSee validation split in the repo's inputs and scoring-only layouts, without reading any label.

    python detector/list_split.py IMAGES LABELS OUT

IMAGES and LABELS hold data/images/val/shard_000 and data/labels/val/shard_000 from the dronefreak/SeaDronesSee mirror
at revision deb1f872. Writes OUT/inputs/manifest.json and OUT/scoring-only/manifest.json in image-number order.
Link the images at OUT/inputs/images and the labels at OUT/scoring-only/labels. Labels are hashed, never parsed.
"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

MIRROR = "https://huggingface.co/datasets/dronefreak/SeaDronesSee/tree/deb1f872ffe7efa4b7ee3a672562d16b6dc0ca5c"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(images, labels, out):
    inputs, scoring = [], []
    for name in sorted((path.stem for path in images.glob("*.jpg")), key=int):
        image = images / f"{name}.jpg"
        with Image.open(image) as im:
            width, height = im.size
        inputs.append(dict(frame=name, image=f"images/{name}.jpg", source=f"shard_000/{name}.jpg",
                           width=width, height=height, sha256=sha256(image)))
        scoring.append(dict(frame=name, label=f"labels/{name}.txt", sha256=sha256(labels / f"{name}.txt")))
    for folder, manifest in (("inputs", dict(dataset="SeaDronesSee detection validation split, every photo",
                                             mirror=MIRROR, frames=inputs)),
                             ("scoring-only", dict(format="YOLO normalized xywh, class 0 = swimmer", frames=scoring))):
        (out / folder).mkdir(parents=True, exist_ok=True)
        (out / folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(len(inputs), "photos listed")


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:4]))
