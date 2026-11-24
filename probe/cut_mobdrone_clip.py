"""Cut a MOBDrone video into the live run's clip, with labels for each second the search tool will cut from it.

    python probe/cut_mobdrone_clip.py DATA_DIR VIDEO FIRST_FRAME CLIP_DIR [--seconds 120] [--out mobdrone/clip]

DATA_DIR holds what fetch_mobdrone.py downloaded. VIDEO is checked against its SHA-256 in mobdrone/frames.json, then
its frames from FIRST_FRAME (counting from 0) on, as many as fill the seconds at the video's frame rate, are encoded
as CLIP_DIR/clip.mp4 at the same constant frame rate. The clip's frame n is the video's frame FIRST_FRAME + n.

open_water_search.py searches a video one frame per second, the frame ffmpeg's fps=1 filter keeps, which is the
last frame before each half second. To label exactly that frame, the same filter runs on a copy of the clip whose
pixels spell each frame's number. Each second's person boxes are written to
CLIP_DIR/scoring-only/labels/second-NNNNN.txt in YOLO format (class 0 = person, as extract_mobdrone.py writes them),
and their MOBDrone track IDs, line by line and null where a box has none, to labels/tracks.json.

CLIP_DIR/scoring-only/manifest.json lists every label file's SHA-256, the SHA-256 of tracks.json and the clip. The
same manifest goes to OUT/scoring-only/manifest.json, with OUT/scoring-only/labels linked to the clip's labels.
"""
import argparse
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from extract_mobdrone import ROOT, check_video, link, people, yolo_label
from fetch_mobdrone import LABELS, MD5, label_name
from select_mobdrone import count_frames


def frames_kept_each_second(clip):
    """The clip frame number that open_water_search.py's cut keeps for each second, in order."""
    with TemporaryDirectory() as scratch:
        # cut_into_seconds() runs -vf fps=1. The same filter here sees frames whose red and green spell their number.
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vf",
                        "scale=8:8,format=gbrp,geq=r='mod(N,256)':g='floor(N/256)':b=0,fps=1",
                        "-start_number", "0", str(Path(scratch) / "%05d.png")], check=True)
        kept = []
        for path in sorted(Path(scratch).iterdir()):
            with Image.open(path) as image:
                red, green, _ = image.convert("RGB").getpixel((0, 0))
            kept.append(red + 256 * green)
    return kept


def main(data, video_name, first_frame, clip_dir, seconds, listing_path, out):
    video = next(v for v in json.loads(listing_path.read_text())["videos"] if v["video"] == video_name)
    frames = round(seconds * Fraction(video["frame_rate"]))
    if first_frame + frames > video["frame_count"]:
        raise SystemExit(f"{seconds} seconds from frame {first_frame} runs past the end of {video_name}")
    check_video(data / "videos" / video_name, video["sha256"])
    clip = clip_dir / "clip.mp4"
    labels = clip_dir / "scoring-only" / "labels"
    labels.mkdir(parents=True, exist_ok=True)
    rate = video["frame_rate"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(data / "videos" / video_name), "-vf",
                    f"trim=start_frame={first_frame}:end_frame={first_frame + frames},setpts=N/({rate})/TB",
                    "-r", rate, "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(clip)], check=True)
    if count_frames(clip)[0] != frames:
        raise SystemExit(f"{clip} does not hold the {frames} frames cut from {video_name}")
    kept = frames_kept_each_second(clip)
    if len(kept) != seconds:
        raise SystemExit(f"the search tool would cut {len(kept)} seconds from {clip}, not {seconds}")
    labeled = people(data / LABELS)
    rows, tracks = [], {}
    for second, clip_frame in enumerate(kept):
        name = f"second-{second:05}"
        width, height, boxes = labeled[label_name(video_name, first_frame + clip_frame)]
        (labels / f"{name}.txt").write_text(yolo_label(width, height, boxes))
        tracks[name] = [track for _, track in boxes]
        rows.append(dict(frame=name, label=f"labels/{name}.txt", video_frame=first_frame + clip_frame,
                         sha256=hashlib.sha256((labels / f"{name}.txt").read_bytes()).hexdigest()))
    (labels / "tracks.json").write_text(json.dumps(tracks, indent=2) + "\n")
    manifest = dict(
        format="YOLO normalized xywh, class 0 = person (MOBDrone's person boxes), one label file per second as "
               "open_water_search.py cuts the clip",
        clip=dict(file="clip.mp4", sha256=hashlib.sha256(clip.read_bytes()).hexdigest(), video=video_name,
                  first_frame=first_frame, frames=frames, frame_rate=rate, seconds=seconds),
        labels=LABELS, labels_md5=MD5[LABELS],
        tracks="labels/tracks.json", tracks_sha256=hashlib.sha256((labels / "tracks.json").read_bytes()).hexdigest(),
        frames=rows)
    for folder in (clip_dir / "scoring-only", out / "scoring-only"):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    link(out / "scoring-only" / "labels", labels)
    print(f"cut {seconds} seconds ({frames} frames) of {video_name} from frame {first_frame} into {clip}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", type=Path, help="folder with videos/ and the MOBDrone label file")
    parser.add_argument("video", help="video file name, as in mobdrone/frames.json")
    parser.add_argument("first_frame", type=int, help="the video's frame number that opens the clip, counting from 0")
    parser.add_argument("clip", type=Path, help="folder for clip.mp4 and scoring-only/, outside the repository")
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--list", type=Path, default=ROOT / "mobdrone" / "frames.json", help="the committed frame list")
    parser.add_argument("--out", type=Path, default=ROOT / "mobdrone" / "clip", help="folder for the committed manifest")
    args = parser.parse_args()
    main(args.data, args.video, args.first_frame, args.clip, args.seconds, args.list, args.out)
