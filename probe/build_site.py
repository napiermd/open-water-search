"""Assemble the public website in site/: the three pages, the sealed-run data, and the 60 frames and labels.

    python probe/fetch_frames.py
    python probe/build_site.py
    vercel deploy site --prod

Frames are resized to 2,400 pixels on the long edge. The pages place every overlay in original-image
coordinates, so resizing changes nothing they show. SeaDronesSee is CC0, so the hosted site may carry the
frames and labels even though the repository does not.
"""
import json
import shutil

from PIL import Image

from score import ROOT, TRAINING, VALIDATION

SITE = ROOT / "site"
LONG_EDGE = 2400
VERCEL = {
    "redirects": [
        {"source": "/", "destination": "/pages/index.html", "permanent": False},
        {"source": "/judge", "destination": "/pages/judge.html", "permanent": False},
        {"source": "/replay", "destination": "/pages/replay.html", "permanent": False},
    ],
    "headers": [
        {"source": "/(.*)\\.jpg", "headers": [{"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}]},
    ],
}


def main():
    SITE.mkdir(exist_ok=True)
    for entry in SITE.iterdir():
        if entry.name != ".vercel":  # keep the Vercel project link between builds
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
    shutil.copytree(ROOT / "pages", SITE / "pages")
    frames = 0
    # The site keeps the layout the pages were built for: the training frames at its root, validation under validation/.
    for base, prefix in ((TRAINING, ""), (VALIDATION, "validation/")):
        labels = {row["frame"]: row["label"] for row in json.loads((base / "scoring-only/manifest.json").read_text())["frames"]}
        for frame in json.loads((base / "inputs/manifest.json").read_text())["frames"]:
            source = base / "inputs" / frame["image"]
            if not source.exists():
                raise SystemExit(f"Missing {source}. Run python probe/fetch_frames.py first.")
            target = SITE / prefix / "inputs" / frame["image"]
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source) as image:
                image = image.convert("RGB")
                image.thumbnail((LONG_EDGE, LONG_EDGE), Image.Resampling.LANCZOS)
                image.save(target, quality=86)
            label = SITE / prefix / "scoring-only" / labels[frame["frame"]]
            label.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base / "scoring-only" / labels[frame["frame"]], label)
            frames += 1
    (SITE / "vercel.json").write_text(json.dumps(VERCEL, indent=2))
    (SITE / ".vercelignore").write_text(".env*\n")  # vercel link writes a token to .env.local; never upload it
    print(f"site/ ready: {frames} frames, the pages and the run data")


if __name__ == "__main__":
    main()
