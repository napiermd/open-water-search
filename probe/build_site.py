"""Assemble the public website, sealed-run data, and the earlier replay frames and labels into site/.

    python probe/fetch_frames.py
    python probe/build_site.py
    vercel deploy site --prod

Frames are resized to 2,400 pixels on the long edge. The pages place every overlay in original-image
coordinates, so resizing changes nothing they show. SeaDronesSee is CC0, so the hosted site may carry the
frames and labels even though the repository does not.
"""
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from score import ROOT, TRAINING, VALIDATION

SITE = ROOT / "site"
LONG_EDGE = 2400
VERCEL = {
    "redirects": [
        {"source": "/", "destination": "/pages/flight.html", "permanent": False},
        {"source": "/judge", "destination": "/pages/flight.html", "permanent": False},
        {"source": "/replay", "destination": "/pages/replay.html", "permanent": False},
    ],
    "headers": [
        {"source": "/(.*)\\.jpg", "headers": [{"key": "Cache-Control", "value": "public, max-age=3600, must-revalidate"}]},
    ],
}


def site_inputs():
    for base, prefix in ((TRAINING, ""), (VALIDATION, "validation/")):
        labels = {row["frame"]: row["label"] for row in json.loads((base / "scoring-only/manifest.json").read_text())["frames"]}
        for frame in json.loads((base / "inputs/manifest.json").read_text())["frames"]:
            image = base / "inputs" / frame["image"]
            label = base / "scoring-only" / labels[frame["frame"]]
            for source in (image, label):
                if not source.is_file():
                    raise SystemExit(f"Missing {source}. Run python probe/fetch_frames.py first.")
            yield image, prefix + "inputs/" + frame["image"], label, prefix + "scoring-only/" + labels[frame["frame"]]


def assemble(staging, inputs):
    shutil.copytree(ROOT / "pages", staging / "pages")
    for image_path, image_name, label_path, label_name in inputs:
        target = staging / image_name
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            image.thumbnail((LONG_EDGE, LONG_EDGE), Image.Resampling.LANCZOS)
            image.save(target, quality=86)
        label = staging / label_name
        label.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(label_path, label)
    (staging / "vercel.json").write_text(json.dumps(VERCEL, indent=2))
    (staging / ".vercelignore").write_text(".env*\n")


def main():
    inputs = list(site_inputs())
    with TemporaryDirectory(prefix=".site-build-", dir=SITE.parent) as folder:
        staging = Path(folder)
        assemble(staging, inputs)
        SITE.mkdir(exist_ok=True)
        for entry in SITE.iterdir():
            if entry.name != ".vercel":  # keep the Vercel project link between builds
                shutil.rmtree(entry) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
        for entry in staging.iterdir():
            entry.rename(SITE / entry.name)
    print(f"site/ ready: {len(inputs)} frames, the pages and the run data")


if __name__ == "__main__":
    main()
