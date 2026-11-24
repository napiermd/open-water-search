"""Choose 30 validation frames from a local copy of the SeaDronesSee mirror at revision deb1f872.

    python select_validation.py PATH_TO_MIRROR/data

The published validation/ folder came from this script. Rerunning it needs the mirror and an empty validation/ folder.
Near-duplicates are checked against the 400 training images listed in inputs/training-pool.txt, the local
training pool from which the November 23 run's frames were drawn.
Choose 30 validation frames without reading any label, and stage them for a sealed Ember run.

Order every validation image by SHA-256 of the seed plus its path. Skip near-duplicates of the
400 local training images (which include all frames used in practice and in the November 23 run)
and of frames already chosen. Label files are copied by byte into the scoring-only folder unread.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "validation"
POOL = Path(__file__).resolve().parents[1] / "inputs/training-pool.txt"
SEED = "open-water-search-validation-2026-11-23"
NEAR = 8  # Hamming distance on a 64-bit difference hash; at or below this counts as a near-duplicate


def dhash(path):
    with Image.open(path) as image:
        small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.get_flattened_data()) if hasattr(small, "get_flattened_data") else list(small.getdata())
    bits = [pixels[row * 9 + col] > pixels[row * 9 + col + 1] for row in range(8) for col in range(8)]
    return sum(bit << i for i, bit in enumerate(bits))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(data):
    if OUT.exists():
        raise SystemExit("Validation set already staged.")
    train = [dhash(data / "images/train" / rel) for rel in POOL.read_text().split()]
    candidates = sorted(
        (p.relative_to(data / "images/val").as_posix() for p in (data / "images/val").rglob("*.jpg")),
        key=lambda rel: hashlib.sha256((SEED + rel).encode()).hexdigest(),
    )
    chosen, chosen_hashes, skipped = [], [], []
    for rel in candidates:
        value = dhash(data / "images/val" / rel)
        nearest = min(bin(value ^ other).count("1") for other in train + chosen_hashes)
        if nearest <= NEAR:
            skipped.append(dict(path=rel, nearest=nearest))
            continue
        chosen.append(rel)
        chosen_hashes.append(value)
        if len(chosen) == 30:
            break
    (OUT / "inputs/images").mkdir(parents=True)
    (OUT / "scoring-only/labels").mkdir(parents=True)
    frames, labels = [], []
    for number, rel in enumerate(chosen, 1):
        name = f"frame-{number:02}"
        image = OUT / "inputs/images" / f"{name}.jpg"
        shutil.copyfile(data / "images/val" / rel, image)
        with Image.open(image) as opened:
            width, height = opened.size
        frames.append(dict(frame=name, image=f"images/{name}.jpg", source=rel, width=width, height=height, sha256=sha(image)))
        label = OUT / "scoring-only/labels" / f"{name}.txt"
        shutil.copyfile(data / "labels/val" / Path(rel).with_suffix(".txt"), label)
        labels.append(dict(frame=name, label=f"labels/{name}.txt", sha256=sha(label)))
    (OUT / "inputs/manifest.json").write_text(json.dumps(dict(
        dataset="SeaDronesSee detection validation split",
        mirror="https://huggingface.co/datasets/dronefreak/SeaDronesSee/tree/deb1f872",
        selection=dict(
            pool=len(candidates),
            seed=SEED,
            method="Order validation paths by SHA-256 of the seed followed by the path relative to images/val. "
                   "Skip any image whose 64-bit difference hash is within 8 bits of a local training image or an earlier pick. Take the first 30.",
            near_duplicates_skipped=skipped,
        ),
        frames=frames,
    ), indent=2))
    (OUT / "scoring-only/manifest.json").write_text(json.dumps(dict(format="YOLO normalized xywh, class 0 = swimmer", frames=labels), indent=2))
    print(f"chose 30 of {len(candidates)}, skipped {len(skipped)} near-duplicates")
    print("manifest sha256", sha(OUT / "inputs/manifest.json"))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
