"""Choose 300 AFO test-split photos for the third-dataset test, from file names alone.

    python runs/verify-afo/select_afo.py DATA_DIR

DATA_DIR holds test.txt, the test split's file list from PART_1 of the AFO release on Hugging Face. Writes
runs/verify-afo/frames.json and refuses to replace it. No image and no label is read.

A photo's clip is its file name up to the last underscore (k2_38.jpg is frame 38 of clip k2). Clips are taken in
order of SHA-256 of seed/clip and given one photo at a time, round after round, until 300 are assigned, never more
than a clip holds. A clip given k photos has its photos, in frame order, cut into k equal stretches, and the photo
from stretch i sits at offset SHA-256 of seed/clip/i modulo the stretch length.
"""
import hashlib
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "frames.json"
SEED = "open-water-search-afo-2026-11-24"
FRAMES = 300


def ordering(*parts):
    return int(hashlib.sha256("/".join([SEED, *map(str, parts)]).encode()).hexdigest(), 16)


def main(data):
    if OUT.exists():
        raise SystemExit(f"{OUT} already exists.")
    listed = (data / "test.txt").read_text().split()
    clips = {}
    for name in listed:
        clip, number = Path(name).stem.rsplit("_", 1)
        clips.setdefault(clip, []).append((int(number), name))
    order = sorted(clips, key=ordering)
    picks = dict.fromkeys(order, 0)
    while sum(picks.values()) < FRAMES:
        for clip in [clip for clip in order if picks[clip] < len(clips[clip])][:FRAMES - sum(picks.values())]:
            picks[clip] += 1
    frames = []
    for clip in sorted(clips):
        pool = [name for _, name in sorted(clips[clip])]
        k = picks[clip]
        for stretch in range(k):
            start, end = stretch * len(pool) // k, (stretch + 1) * len(pool) // k
            frames.append(dict(clip=clip, image=pool[start + ordering(clip, stretch) % (end - start)]))
    OUT.write_text(json.dumps(dict(
        dataset="AFO: Aerial dataset of Floating Objects (Gasienica-Jozkowy, Knapik and Cyganek, 2021)",
        source="https://huggingface.co/datasets/jgasienica/afo-dataset",
        license="CC BY-NC-SA 3.0, used non-commercially",
        split="test.txt", split_sha256=hashlib.sha256((data / "test.txt").read_bytes()).hexdigest(),
        selection=dict(seed=SEED, frames=FRAMES, method=__doc__.split("\n\n")[2].strip()),
        clips={clip: dict(photos=len(clips[clip]), chosen=picks[clip]) for clip in sorted(clips)},
        frames=frames,
    ), indent=2) + "\n")
    print(f"chose {len(frames)} photos from {sum(1 for k in picks.values() if k)} of {len(clips)} clips")
    print("frame list sha256", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
