"""Extract the 300 MOBDrone frames listed in mobdrone/frames.json as a flight folder, and list them in the repo's layouts.

    python probe/extract_mobdrone.py DATA_DIR SAMPLE_DIR [--list mobdrone/frames.json] [--out mobdrone]

DATA_DIR holds what fetch_mobdrone.py downloaded: videos/ and annotations_person_coco_classes.json. Every video is
checked against its SHA-256 in the frame list first. Each chosen frame is taken by its frame number, counting from 0
in display order (the n of ffmpeg's select filter), never by its time, and saved as
SAMPLE_DIR/images/NNN-VIDEO-FRAME.jpg, where NNN is its place in the frame list, so the photos sort in the list's
order and the folder searches as a flight. The frame's person boxes become SAMPLE_DIR/labels/NNN-VIDEO-FRAME.txt in
YOLO format: class 0 and the box's center x, center y, width and height as fractions of the frame. Person is the
only class in MOBDrone's label file, and class 0 is the class the scorer counts as a swimmer.

Writes OUT/inputs/manifest.json, each photo with its size and the SHA-256 of its JPEG, and
OUT/scoring-only/manifest.json, each label file's SHA-256, then links OUT/inputs/images and OUT/scoring-only/labels
to the folders in SAMPLE_DIR. The photos and labels stay out of the repository.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from fetch_mobdrone import LABELS, MD5, digest, label_name

ROOT = Path(__file__).resolve().parents[1]


def people(labels):
    """MOBDrone's person boxes by label image name: (width, height, [(COCO box [x, y, w, h], track ID or None)])."""
    coco = json.loads(labels.read_text())
    by_id = {image["id"]: (image["width"], image["height"], []) for image in coco["images"]}
    for box in coco["annotations"]:
        by_id[box["image_id"]][2].append((box["bbox"], box.get("attributes", {}).get("track_id")))
    return {image["file_name"]: by_id[image["id"]] for image in coco["images"]}


def yolo_label(width, height, boxes):
    """One line per person box: class 0, then center x, center y, width and height as fractions of the frame."""
    return "".join(f"0 {(x + w / 2) / width:.6f} {(y + h / 2) / height:.6f} {w / width:.6f} {h / height:.6f}\n"
                   for (x, y, w, h), _ in boxes)


def check_video(path, sha256):
    if digest(path, "sha256") != sha256:
        raise SystemExit(f"{path.name} does not match the SHA-256 in the frame list")


def extract(video, frame_numbers, folder):
    """Save the frames with these numbers (in increasing order) as JPEGs in folder. Returns their paths in order."""
    chosen = "+".join(f"eq(n,{n})" for n in frame_numbers)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"select='{chosen}'", "-fps_mode", "passthrough",
                    "-frames:v", str(len(frame_numbers)), "-qscale:v", "2", "-start_number", "0",
                    str(folder / "%03d.jpg")], check=True)
    paths = [folder / f"{index:03}.jpg" for index in range(len(frame_numbers))]
    if not all(path.exists() for path in paths):
        raise SystemExit(f"ffmpeg returned fewer than {len(frame_numbers)} frames from {video.name}")
    return paths


def link(path, target):
    if path.is_symlink():
        path.unlink()
    path.symlink_to(target.resolve(), target_is_directory=True)


def main(data, sample, listing_path, out):
    listing = json.loads(listing_path.read_text())
    for video in listing["videos"]:
        check_video(data / "videos" / video["video"], video["sha256"])
    labeled = people(data / LABELS)
    images, labels = sample / "images", sample / "labels"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    inputs, scoring = [], []
    places = {(frame["video"], frame["frame"]): place for place, frame in enumerate(listing["frames"], 1)}
    for video in listing["videos"]:
        numbers = sorted(frame for name, frame in places if name == video["video"])
        with TemporaryDirectory() as scratch:
            extracted = extract(data / "videos" / video["video"], numbers, Path(scratch))
            for number, path in zip(numbers, extracted):
                name = f"{places[video['video'], number]:03}-{Path(video['video']).stem}-{number:06}"
                path.replace(images / f"{name}.jpg")
                width, height, boxes = labeled[label_name(video["video"], number)]
                with Image.open(images / f"{name}.jpg") as image:
                    if image.size != (width, height):
                        raise SystemExit(f"{name}.jpg is {image.size}, but its labels are for {width} x {height}")
                (labels / f"{name}.txt").write_text(yolo_label(width, height, boxes))
                inputs.append(dict(frame=name, image=f"images/{name}.jpg", video=video["video"], video_frame=number,
                                   width=width, height=height,
                                   sha256=hashlib.sha256((images / f"{name}.jpg").read_bytes()).hexdigest()))
                scoring.append(dict(frame=name, label=f"labels/{name}.txt",
                                    sha256=hashlib.sha256((labels / f"{name}.txt").read_bytes()).hexdigest()))
    inputs.sort(key=lambda row: row["frame"])
    scoring.sort(key=lambda row: row["frame"])
    manifests = {
        "inputs": dict(dataset=listing["dataset"], source=listing["source"], license=listing["license"],
                       list="mobdrone/frames.json", list_sha256=hashlib.sha256(listing_path.read_bytes()).hexdigest(),
                       extraction="ffmpeg select by frame number counting from 0, saved as JPEG at -qscale:v 2",
                       frames=inputs),
        "scoring-only": dict(format="YOLO normalized xywh, class 0 = person (MOBDrone's person boxes)",
                             labels=LABELS, labels_md5=MD5[LABELS], frames=scoring),
    }
    for folder, manifest in manifests.items():
        (out / folder).mkdir(parents=True, exist_ok=True)
        (out / folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    link(out / "inputs" / "images", images)
    link(out / "scoring-only" / "labels", labels)
    print(f"extracted {len(inputs)} frames from {len(listing['videos'])} videos into {images}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", type=Path, help="folder with videos/ and the MOBDrone label file")
    parser.add_argument("sample", type=Path, help="folder for images/ and labels/, outside the repository")
    parser.add_argument("--list", type=Path, default=ROOT / "mobdrone" / "frames.json", help="the committed frame list")
    parser.add_argument("--out", type=Path, default=ROOT / "mobdrone", help="folder for inputs/ and scoring-only/")
    args = parser.parse_args()
    main(args.data, args.sample, args.list, args.out)
