"""Choose the 300 MOBDrone frames for the unseen-footage comparison from video names and frame counts alone.

    python select_mobdrone.py DATA_DIR/videos [OUTPUT]

Writes mobdrone/frames.json unless OUTPUT is given, and refuses to replace an existing list. No frame image and
no label is read: ffprobe counts each video's frames and reports its frame rate, and nothing else about the
footage is used. Frames with nobody in them stay in the list.

Every video gives 4 frames, and the 36 videos that come first when ordered by SHA-256 of the seed and the video
name give a fifth, making 300. A video giving k frames is cut into k equal stretches by frame number, and one
frame is taken from each stretch at an offset set by SHA-256 of the seed, the video name and the stretch number.
Frame numbers count from 0 in display order, the n of ffmpeg's select filter. Times are frame number over frame rate.
"""
import hashlib
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "mobdrone/frames.json"
SEED = "open-water-search-mobdrone-2026-11-24"
FRAMES = 300
VIDEOS = 66


def ordering(*parts):
    return int(hashlib.sha256("/".join([SEED, *map(str, parts)]).encode()).hexdigest(), 16)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def count_frames(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames,avg_frame_rate", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["nb_read_frames"]), stream["avg_frame_rate"]


def main(folder, out):
    if out.exists():
        raise SystemExit(f"{out} already exists.")
    paths = sorted(path for path in folder.iterdir() if path.is_file() and not path.name.startswith("."))
    if len(paths) != VIDEOS:
        raise SystemExit(f"Expected {VIDEOS} videos in {folder}, found {len(paths)}.")
    by_order = sorted((path.name for path in paths), key=ordering)
    extra = set(by_order[:FRAMES % VIDEOS])
    videos, frames = [], []
    for path in paths:
        count, rate = count_frames(path)
        videos.append(dict(video=path.name, sha256=sha(path), frame_count=count, frame_rate=rate))
        picks = FRAMES // VIDEOS + (path.name in extra)
        for stretch in range(picks):
            start, end = stretch * count // picks, (stretch + 1) * count // picks
            frame = start + ordering(path.name, stretch) % (end - start)
            frames.append(dict(video=path.name, frame=frame, time=round(float(frame / Fraction(rate)), 3)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(
        dataset="MOBDrone: a large-scale drone-view dataset for man overboard detection (Cafarelli et al., 2022)",
        source="https://doi.org/10.5281/zenodo.5996890",
        license="CC BY 4.0",
        selection=dict(
            seed=SEED,
            frames=FRAMES,
            method="Every video gives 4 frames; the 36 videos first in order of SHA-256 of seed/video give a fifth. "
                   "A video giving k frames is cut into k equal stretches by frame number, and the frame taken from "
                   "stretch i sits at offset SHA-256 of seed/video/i modulo the stretch length. Only video names and "
                   "ffprobe frame counts were used. Frame numbers count from 0; time is frame number over frame rate.",
        ),
        videos=videos,
        frames=frames,
    ), indent=2) + "\n")
    print(f"chose {len(frames)} frames from {len(videos)} videos")
    print("frame list sha256", sha(out))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else OUT)
