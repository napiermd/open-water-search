"""Cut every MOBDrone video into one frame per second, the way the search tool cuts a flight, and list the frames.

    python experiments/lost-people/flight-ranking/cut_flights.py DATA_DIR SECONDS_DIR

DATA_DIR holds what probe/fetch_mobdrone.py downloaded. Each video in DATA_DIR/videos is cut with the same ffmpeg
filter as open_water_search.py's cut_into_seconds(), into SECONDS_DIR/VIDEO/second-NNNNN.jpg. The video frame each
second keeps is read the way probe/cut_mobdrone_clip.py reads it, so a later test can find that frame's labels.

inputs/manifest.json beside this script lists every second with its video, second, video frame, size and SHA-256,
in the layout detector/run_detector.py reads. inputs/images is linked to SECONDS_DIR. No label is read.
"""
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "probe"))
from cut_mobdrone_clip import frames_kept_each_second  # noqa: E402
from extract_mobdrone import link  # noqa: E402


def cut(video, folder):
    """Cut one video into folder and return a manifest row for each second."""
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-vf", "fps=1", "-qscale:v", "2",
                    "-start_number", "0", str(folder / "second-%05d.jpg")], check=True)
    kept = frames_kept_each_second(video)
    paths = sorted(folder.glob("second-*.jpg"))
    if len(paths) != len(kept):
        raise SystemExit(f"{video.name}: {len(paths)} seconds cut but {len(kept)} frame numbers read")
    rows = []
    for second, (path, video_frame) in enumerate(zip(paths, kept)):
        with Image.open(path) as image:
            width, height = image.size
        rows.append(dict(frame=f"{video.stem}-second-{second:05}", image=f"images/{video.stem}/{path.name}",
                         video=video.name, second=second, video_frame=video_frame, width=width, height=height,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return rows


def main(data, seconds_dir):
    videos = sorted((data / "videos").glob("*.mp4"))
    with ThreadPoolExecutor(4) as pool:
        per_video = list(pool.map(lambda video: cut(video, seconds_dir / video.stem), videos))
    inputs = HERE / "inputs"
    inputs.mkdir(exist_ok=True)
    link(inputs / "images", seconds_dir)
    frames = [row for rows in per_video for row in rows]
    manifest = dict(dataset="MOBDrone (Cafarelli et al., 2022)", source="https://doi.org/10.5281/zenodo.5996890",
                    license="CC BY 4.0", extraction="one frame per second of every video, ffmpeg -vf fps=1 -qscale:v 2, "
                    "as open_water_search.py cuts a flight", videos=len(videos), frames=frames)
    (inputs / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{len(frames)} seconds from {len(videos)} videos")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]).resolve())
