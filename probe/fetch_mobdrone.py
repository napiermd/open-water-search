"""Download the MOBDrone videos and people-only labels from Zenodo and check every hash.

    python fetch_mobdrone.py DATA_DIR

MOBDrone (Cafarelli et al., 2022, https://doi.org/10.5281/zenodo.5996890) is released under CC BY 4.0 and stays
outside this repository. Downloads MOBDrone_videos.zip and annotations_person_coco_classes.json into DATA_DIR and
checks each against the MD5 Zenodo publishes, then unpacks the 66 videos into DATA_DIR/videos and checks each
against the SHA-256 in mobdrone/frames.json. Files already present with the right hash are skipped.
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
    print(f"{len(listing['videos'])} videos match mobdrone/frames.json; {LABELS} matches Zenodo's MD5")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
