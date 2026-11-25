"""Write a flight's position file for SeaDronesSee frames from the dataset's official annotations.

    python3 probe/write_positions.py instances_val.json experiments/zoom-first/validation-30/inputs/manifest.json experiments/zoom-first/validation-30/inputs/positions.json
    python3 probe/open_water_search.py experiments/zoom-first/validation-30/inputs/images --out results --positions experiments/zoom-first/validation-30/inputs/positions.json

instances_val.json is the Object Detection v2 validation annotation file the SeaDronesSee authors publish under
CC0 1.0. Download it without registration from
https://raw.githubusercontent.com/Ben93kie/SeaDronesSee/main/OD/evaluation%20of%20OD%20V2/required%20files/instances_val.json

A manifest frame whose source is shard_000/<N>.jpg is image id N in that file, and the image's meta holds the
drone's telemetry when the photo was taken. The position file keeps the drone's latitude and longitude with that
meta. A frame whose meta is null gets null, so it has no position.
"""
import argparse
import json
from pathlib import Path

SOURCE = ("SeaDronesSee Object Detection v2 instances_val.json, image meta (CC0 1.0): "
          "https://github.com/Ben93kie/SeaDronesSee/blob/main/OD/evaluation%20of%20OD%20V2/required%20files/instances_val.json")


def drone_position(meta):
    """The drone's latitude and longitude from one image's meta, kept with the meta itself.

    Video frames give latitude and longitude. Still photos give gps_latitude and gps_longitude with a hemisphere
    letter in the _ref fields, or, in most of them, the number itself in the _ref fields.
    """
    if meta.get("gps_latitude_ref") == "S" or meta.get("gps_longitude_ref") == "W":
        raise SystemExit("This reader takes the numbers as north and east, and this image is south or west.")
    latitude = next(meta[name] for name in ("latitude", "gps_latitude", "gps_latitude_ref")
                    if isinstance(meta.get(name), (int, float)))
    longitude = next(meta[name] for name in ("longitude", "gps_longitude", "gps_longitude_ref")
                     if isinstance(meta.get(name), (int, float)))
    return dict(latitude=latitude, longitude=longitude, meta=meta)


def main(arguments=None):
    parser = argparse.ArgumentParser(description="Write a position file for SeaDronesSee frames.")
    parser.add_argument("annotations", type=Path, help="the official instances_val.json")
    parser.add_argument("manifest", type=Path, help="manifest whose frames name their source, such as shard_000/10833.jpg")
    parser.add_argument("out", type=Path, help="position file to write")
    args = parser.parse_args(arguments)
    images = {image["id"]: image for image in json.loads(args.annotations.read_text())["images"]}
    frames = {}
    for frame in json.loads(args.manifest.read_text())["frames"]:
        meta = images[int(Path(frame["source"]).stem)]["meta"]
        frames[frame["frame"]] = drone_position(meta) if meta else None
    args.out.write_text(json.dumps(dict(source=SOURCE, frames=frames), indent=2) + "\n")
    placed = sum(position is not None for position in frames.values())
    print(f"{placed} of {len(frames)} frames have a drone position. Wrote {args.out}")


if __name__ == "__main__":
    main()
