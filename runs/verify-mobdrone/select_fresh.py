"""Choose 300 MOBDrone frames that no earlier run used, from video names and frame counts alone.

    python runs/verify-mobdrone/select_fresh.py

Writes runs/verify-mobdrone/frames.json and refuses to replace it. No frame image and no label is read. Frame counts
and rates come from mobdrone/frames.json, which ffprobe measured for the first 300.

A frame is eligible if it is more than GAP frames (about two seconds) from each of the first 300 frames and from the
live clip's stretch of DJI_0915_0007_40.mp4. Videos are taken in order of SHA-256 of seed/video and given one frame
at a time, round after round, until 300 are assigned. A video gets another frame only while it has at least GAP
eligible frames per frame assigned, so short videos give fewer or none. A video given k frames has its eligible frames
cut into k equal stretches, and the frame from stretch i sits at offset SHA-256 of seed/video/i modulo the stretch
length.
"""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "frames.json"
SEED = "open-water-search-mobdrone-fresh-2026-11-24"
FRAMES = 300
GAP = 60


def ordering(*parts):
    return int(hashlib.sha256("/".join([SEED, *map(str, parts)]).encode()).hexdigest(), 16)


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} already exists.")
    first = json.loads((ROOT / "mobdrone/frames.json").read_text())
    clip = json.loads((ROOT / "mobdrone/clip/scoring-only/manifest.json").read_text())["clip"]
    seen = {}
    for frame in first["frames"]:
        seen.setdefault(frame["video"], []).append((frame["frame"], frame["frame"]))
    seen.setdefault(clip["video"], []).append((clip["first_frame"], clip["first_frame"] + clip["frames"] - 1))
    videos = first["videos"]
    eligible = {video["video"]: [frame for frame in range(video["frame_count"])
                                 if all(frame < low - GAP or frame > high + GAP
                                        for low, high in seen.get(video["video"], []))]
                for video in videos}
    order = sorted(eligible, key=ordering)
    picks = dict.fromkeys(order, 0)
    while sum(picks.values()) < FRAMES:
        open_videos = [name for name in order if (picks[name] + 1) * GAP <= len(eligible[name])]
        if not open_videos:
            raise SystemExit("Not enough eligible frames.")
        for name in open_videos[:FRAMES - sum(picks.values())]:
            picks[name] += 1
    frames = []
    for video in videos:
        name, pool, k = video["video"], eligible[video["video"]], picks[video["video"]]
        for stretch in range(k):
            start, end = stretch * len(pool) // k, (stretch + 1) * len(pool) // k
            frame = pool[start + ordering(name, stretch) % (end - start)]
            frames.append(dict(video=name, frame=frame, time=round(float(frame / Fraction(video["frame_rate"])), 3)))
    OUT.write_text(json.dumps(dict(
        dataset=first["dataset"], source=first["source"], license=first["license"],
        selection=dict(seed=SEED, frames=FRAMES, gap_frames=GAP, method=__doc__.split("\n\n")[3].strip()),
        videos=videos, frames=frames,
    ), indent=2) + "\n")
    print(f"chose {len(frames)} frames from {sum(1 for k in picks.values() if k)} of {len(videos)} videos")
    print("frame list sha256", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
