"""Download the MOBDrone videos and people-only labels from Zenodo and check every hash.

    python fetch_mobdrone.py DATA_DIR

MOBDrone (Cafarelli et al., 2022, https://doi.org/10.5281/zenodo.5996890) is released under CC BY 4.0 and stays
outside this repository. Downloads MOBDrone_videos.zip and annotations_person_coco_classes.json into DATA_DIR and
checks each against the MD5 Zenodo publishes, then unpacks the 66 videos into DATA_DIR/videos and checks each
against the SHA-256 in mobdrone/frames.json. Files already present with the right hash are skipped.

Finally it checks that the label file parses and lists one image per frame of every video, named
VIDEO_FRAME.PNG with the frame number in six digits counting from 0, so every chosen frame has its label entry.
The video DJI_0915_0007_40.mp4 appears in the label file as DJI_0915_0007_40m.
"""
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

LIST = Path(__file__).resolve().parents[1] / "mobdrone/frames.json"
RECORD = "https://zenodo.org/api/records/5996890/files"
VIDEOS = "MOBDrone_videos.zip"
LABELS = "annotations_person_coco_classes.json"
MD5 = {VIDEOS: "250c19fdd6fb0b5aa5fa43e5ad140306", LABELS: "c3c97f5518440489e686b63525fb6d3e"}
LABEL_STEMS = {"DJI_0915_0007_40.mp4": "DJI_0915_0007_40m"}


def label_name(video, frame):
    return f"{LABEL_STEMS.get(video, Path(video).stem)}_{frame:06}.PNG"


def digest(path, algorithm):
    hasher = hashlib.new(algorithm)
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def fetch(data, name):
    path = data / name
    if path.exists() and digest(path, "md5") == MD5[name]:
        return path
    partial = data / f"{name}.part"
    with urllib.request.urlopen(f"{RECORD}/{name}/content", timeout=120) as response, partial.open("wb") as file:
        shutil.copyfileobj(response, file, 1 << 20)
    if digest(partial, "md5") != MD5[name]:
        raise SystemExit(f"MD5 mismatch for {name}")
    partial.replace(path)
    return path


def unpack(archive, folder):
    folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as opened:
        for member in opened.infolist():
            name = Path(member.filename).name
            if member.is_dir() or name.startswith(".") or "__MACOSX" in member.filename:
                continue
            target = folder / name
            if target.exists() and target.stat().st_size == member.file_size:
                continue
            with opened.open(member) as source, target.open("wb") as file:
                shutil.copyfileobj(source, file, 1 << 20)


def main(data):
    data.mkdir(parents=True, exist_ok=True)
    archive = fetch(data, VIDEOS)
    fetch(data, LABELS)
    unpack(archive, data / "videos")
    if not LIST.exists():
        print(f"{VIDEOS} and {LABELS} match Zenodo's MD5; videos unpacked to {data / 'videos'}")
        return
    listing = json.loads(LIST.read_text())
    for video in listing["videos"]:
        if digest(data / "videos" / video["video"], "sha256") != video["sha256"]:
            raise SystemExit(f"SHA-256 mismatch for {video['video']}")
    labelled = {image["file_name"] for image in json.loads((data / LABELS).read_text())["images"]}
    counted = {label_name(video["video"], frame) for video in listing["videos"] for frame in range(video["frame_count"])}
    if labelled != counted:
        raise SystemExit(f"{LABELS} does not list exactly the {len(counted)} frames ffprobe counted")
    chosen = {label_name(frame["video"], frame["frame"]) for frame in listing["frames"]}
    print(f"{len(listing['videos'])} videos match mobdrone/frames.json; {LABELS} matches Zenodo's MD5")
    print(f"{LABELS} lists all {len(counted)} frames, including the {len(chosen & labelled)} chosen")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
