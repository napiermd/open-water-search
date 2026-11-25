"""Build the public field examples from the verified offline flight and its scoring folder."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from PIL import Image

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
sys.path.insert(0, str(ROOT / "probe"))
from check_merge_rule import holder, labeled_people
from export_handoff import render
from flag_check import crop_square

ATTRIBUTION = "MOBDrone, Cafarelli et al. (2022), CC BY 4.0. Frame resized for display. doi.org/10.5281/zenodo.5996890"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verified", type=Path)
    parser.add_argument("labels", type=Path)
    args = parser.parse_args()
    out = ROOT / "pages/flight"
    out.mkdir(exist_ok=True)
    record = json.loads((RUN / "search-record-redacted.json").read_text())
    replay = json.loads((args.verified / "search-record.json").read_text())
    for key in ("possible_people", "coverage_timeline"):
        if replay[key] != record[key]:
            raise ValueError(f"Replayed {key} differs from the published run")
    timeline = {r["frame"]: r for r in record["coverage_timeline"]}
    labels = labeled_people(args.labels, list(timeline.values()))

    def evidence(frame, flag):
        width, height = frame["width"], frame["height"]
        box = flag["box"]
        x, y = (box[0]+box[2])/2, (box[1]+box[3])/2
        track = holder(dict(x=x, y=y), labels[frame["frame"]])
        if not track or track[0] is None:
            raise ValueError("Selected pin must be traceable to a labeled person")
        photo = frame["frame"] + ".webp"
        with Image.open(args.verified / "frames" / (frame["frame"] + ".jpg")) as img:
            img.thumbnail((1280, 1280))
            img.save(out / photo, quality=86)
        crop = Path(flag["crop"]).name
        shutil.copyfile(args.verified / flag["crop"], out / crop)
        return dict(second=frame["second"], width=width, height=height, photo=photo, crop=crop, pin=[x,y],
                    rect=crop_square(width,height,box), label=track[1], track=track[0], description=flag["what"])

    handoffs = []
    for person in record["possible_people"]:
        last = person["sightings"][-1]
        frame = timeline[last["frame"]]
        flag = next(f for f in frame["flags"] if f["crop"] == last["crop"] and f["status"] == "kept")
        number = person["number"]
        packet = f"handoff-{number}.html"
        (out / packet).write_text(render(args.verified, record, number, ATTRIBUTION))
        handoffs.append(dict(**evidence(frame,flag), number=number, first=person["first_seen_second"],
                             section=person["position"]["section"], handoff=person["handoff_message"], packet=packet))
    frame = timeline["second-00012"]
    flag = frame["flags"][0]
    if flag["status"] != "dismissed":
        raise ValueError("Expected a recorded dismissal")
    miss = evidence(frame, flag)
    if miss["track"] != handoffs[0]["track"]:
        raise ValueError("The two pinned images must show the same labeled track")
    (out / "record.json").write_text(json.dumps(dict(handoffs=handoffs, missed=miss), indent=2)+"\n")


if __name__ == "__main__":
    main()
