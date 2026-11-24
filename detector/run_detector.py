"""Run a SeaDronesSee-trained YOLO26m detector on a list of photos and write its boxes for probe/score.py.

    python detector/run_detector.py INPUTS_MANIFEST OUT_DIR [--tiles] [--weights PATH] [--device mps]

INPUTS_MANIFEST lists photos as {frame, image, width, height, sha256}, with image relative to the manifest's folder.
OUT_DIR gets boxes.json, one {frame, width, height, boxes} per photo with boxes [x1, y1, x2, y2, confidence, class]
in original-image pixels, and seal.json. Without --tiles each photo goes to the model whole. With --tiles it goes as
the nine tiles of probe/runner.py's 3 x 3 grid, the same tiles Ember gets close looks at. Either way the model sees
each image at 640 pixels, the size it was trained at.

The checkpoint downloads on first use from a pinned Hugging Face commit and is checked against its SHA-256.
This folder is AGPL-3.0 (see LICENSE). The search tool imports nothing from it.
"""
import argparse
import hashlib
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "probe"))
from runner import rectangle  # noqa: E402  the 3 x 3 tiles Ember's close looks use

WEIGHTS_URL = ("https://huggingface.co/dronefreak/seadronessee-yolo26m/resolve/"
               "288991d42fb719370619b0a30132017a0c8ab5e9/best.pt")
WEIGHTS_SHA256 = "97e29aa81bcc605ebdf14b6ea8a2f2f4606df0236f3f1b2ab1cffbd7a8542847"
IMAGE_SIZE = 640
MIN_CONFIDENCE = 0.25


def detect(predict, image, tiles):
    """Boxes for one photo, moved from each tile's pixels to the photo's."""
    width, height = image.size
    rects = [rectangle(width, height, tile) for tile in (range(9) if tiles else [-1])]
    boxes = []
    for (left, top, _, _), found in zip(rects, predict([image.crop(rect) for rect in rects])):
        boxes += [[round(x1 + left, 2), round(y1 + top, 2), round(x2 + left, 2), round(y2 + top, 2),
                   round(confidence, 4), int(cls)] for x1, y1, x2, y2, confidence, cls in found]
    return boxes


def run(inputs, out, tiles, predict, model):
    """Write boxes.json for every photo in the inputs manifest, and seal.json with the SHA-256 of both lists.

    predict takes a list of images and returns, for each, its boxes [x1, y1, x2, y2, confidence, class] in that
    image's pixels. model describes the detector and its settings for the seal.
    Raises ValueError for a photo whose bytes or size differ from the inputs manifest."""
    listed = inputs.read_bytes()
    photos = []
    for f in json.loads(listed)["frames"]:
        raw = (inputs.parent / f["image"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != f["sha256"]:
            raise ValueError(f"{f['image']} does not match the inputs manifest")
        with Image.open(io.BytesIO(raw)) as image:
            if image.size != (f["width"], f["height"]):
                raise ValueError(f"{f['image']} is not the size the inputs manifest lists")
            boxes = detect(predict, image.convert("RGB"), tiles)
        photos.append(dict(frame=f["frame"], width=f["width"], height=f["height"], boxes=boxes))
    data = json.dumps(photos).encode()
    out.mkdir(parents=True, exist_ok=True)
    (out / "boxes.json").write_bytes(data)
    seal = dict(boxes="boxes.json", boxes_sha256=hashlib.sha256(data).hexdigest(),
                inputs=os.path.relpath(inputs, ROOT), inputs_sha256=hashlib.sha256(listed).hexdigest(),
                photos=len(photos), tiles="3 x 3, as probe/runner.py rectangle()" if tiles else "whole photo",
                model=model)
    (out / "seal.json").write_text(json.dumps(seal, indent=2) + "\n")


def fetch_weights(path):
    """Download the pinned checkpoint unless path already holds it, then check its SHA-256."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".part")
        urllib.request.urlretrieve(WEIGHTS_URL, partial)
        partial.rename(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != WEIGHTS_SHA256:
        raise ValueError(f"{path} is not the pinned checkpoint")
    return path


def yolo(weights, device):
    """predict() for the checkpoint, sending each image alone at 640 pixels and keeping boxes at 0.25 confidence
    or more, and the seal's description of the model."""
    # Imported here so the tests and the search tool's checks run without ultralytics installed.
    import torch
    import ultralytics

    if device == "mps" and not torch.backends.mps.is_available():
        sys.exit("MPS is not available. Run outside the Codex sandbox, or pass --device cpu.")
    model = ultralytics.YOLO(weights)

    def predict(images):
        return [model.predict(image, imgsz=IMAGE_SIZE, conf=MIN_CONFIDENCE, device=device, verbose=False)[0]
                .boxes.data.cpu().tolist() for image in images]

    about = dict(checkpoint=WEIGHTS_URL, sha256=WEIGHTS_SHA256, classes=model.names,
                 selected_on="SeaDronesSee val split (the checkpoint's training run picked best.pt on it)",
                 image_size=IMAGE_SIZE, min_confidence=MIN_CONFIDENCE, device=device,
                 ultralytics=ultralytics.__version__, torch=torch.__version__)
    return predict, about


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", type=Path, help="inputs manifest.json")
    parser.add_argument("out", type=Path, help="folder for boxes.json and seal.json")
    parser.add_argument("--tiles", action="store_true", help="send the nine 3 x 3 tiles instead of the whole photo")
    parser.add_argument("--weights", type=Path, default=ROOT / "detector" / "weights" / "seadronessee-yolo26m-best.pt")
    parser.add_argument("--device", default="mps")
    args = parser.parse_args()
    predict, about = yolo(fetch_weights(args.weights), args.device)
    run(args.inputs.resolve(), args.out, args.tiles, predict, about)


if __name__ == "__main__":
    main()
