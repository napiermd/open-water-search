"""Export one recorded sighting to a self-contained HTML file that opens offline.

    python probe/export_handoff.py results 1 --out sighting-1.html
"""
import argparse
import base64
from html import escape
import json
from pathlib import Path


def data_uri(folder, relative):
    path = (folder / relative).resolve()
    if not path.is_relative_to(folder.resolve()):
        raise ValueError("The image must be inside the recorded flight folder")
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def render(folder, record, number, attribution=""):
    person = next((p for p in record["possible_people"] if p["number"] == number), None)
    if person is None:
        raise ValueError(f"No handoff numbered {number} in this flight")
    pin = person["sightings"][-1]
    frame = next(row for row in record["coverage_timeline"] if row["frame"] == pin["frame"])
    photo = data_uri(folder, f'frames/{pin["frame"]}.jpg')
    crop = data_uri(folder, pin["crop"])
    x = 100 * pin["x"] / frame["width"]
    y = 100 * pin["y"] / frame["height"]
    title = f"Possible person {number}"
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Open Water Search</title>
<style>
*{{box-sizing:border-box}}body{{margin:1.5rem auto;padding:0 1rem;max-width:62rem;font:1rem/1.5 system-ui;color:#172f2e;background:#f5f3eb}}
h1{{font:2.4rem Georgia,serif;margin:.6rem 0}}h2{{font-size:1.1rem}}p{{max-width:70ch}}figure{{margin:1rem 0}}
.scene{{position:relative}}img{{display:block;width:100%}}.pin{{position:absolute;width:22px;height:22px;border:3px solid #fff;border-radius:50%;outline:2px solid #153d34;transform:translate(-50%,-50%)}}
.crop{{width:min(100%,224px)}}figcaption,footer{{margin-top:.5rem}}footer{{border-top:1px solid;padding-top:.6rem}}
</style><main><header>Open Water Search · Recorded handoff</header><h1>{title}</h1>
<p>{escape(person["handoff_message"])}</p>
<figure><div class="scene"><img alt="Full drone frame" src="{photo}"><span class="pin" style="left:{x:.5f}%;top:{y:.5f}%"></span></div>
<figcaption>Last reported pin on {escape(pin["frame"])}. It lies {x:.1f}% from the left and {y:.1f}% from the top of the frame.</figcaption></figure>
<h2>Reported crop</h2><img class="crop" src="{crop}" alt="Saved close look for this sighting">
<p>The pin gives an image location. Use the recorded frame and time to return to it in the flight.</p>
<footer>{escape(attribution)}</footer></main></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("number", type=int)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--attribution", default="")
    args = parser.parse_args()
    record = json.loads((args.folder / "search-record.json").read_bytes())
    args.out.write_text(render(args.folder, record, args.number, args.attribution), encoding="utf-8")


if __name__ == "__main__":
    main()
