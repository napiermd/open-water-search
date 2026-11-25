# Run it and reproduce it

How to run the tool on your own flight, serve the pages, and rebuild every published number from its sealed run.

## Run it on your own flight

~~~
pip install pillow
export MODEL_API_KEY=your-meta-model-api-key
python probe/open_water_search.py flight.mp4 --out results --budget 0.10
open results/report.html
~~~

Point it at a flight: a video file, which the tool cuts into one frame per second with ffmpeg, or a folder of .jpg, .jpeg or .png photos whose file names put them in time order, one photo per second. Sightings at most two seconds apart and within 10% of the frame width of each other become one possible person, and the tool prints a handoff message for each. Use `--looks` to change the close looks per frame, `--parallel` to change how many requests run at once (default 8), `--format frozen` for the original prompts, and `--key-file` instead of the environment variable if you prefer. The tool spaces requests out when Meta's rate-limit headers run low, and after a 429 it waits at least the Retry-After time, then backs off with jitter. If the spending cap is reached, the tool stops and says so in the search record and the report. A request that times out, drops its connection or gets a 5xx reply is retried once. If it fails again, only its own overview or tile is lost, and the run continues. Ten unreadable answers in a row, or any other failure, end the run: the tool writes the search record and the report for everything finished so far, then exits with status 1.

If the flight has the drone's GPS position for its photos, pass it with `--positions positions.json`: a JSON file whose `frames` object maps each photo's name (without extension, or `second-00000`, `second-00001` and so on for a video) to `{"latitude": ..., "longitude": ...}` in decimal degrees, or to `null` when that photo has none. Each handoff message then gives the drone position at sighting, and the report maps where the drone was. The tool doesn't compute the person's own coordinates, because the flight data has no camera field of view and measures altitude from the takeoff point. Photos without position data get no coordinates. Without the file, the search record says position data was unavailable and the report shows no map. `probe/write_positions.py` writes this file for SeaDronesSee frames from the dataset's CC0 `instances_val.json`, and `experiments/zoom-first/validation-30/inputs/positions.json` is its output for the 30 validation photos, 22 of which have a position.

Add `--mode detector-check` to have the trained detector flag every frame first and Ember check each flag. It needs a Python with ultralytics for the detector, passed as `--detector-python`, and the detector runs as its own program, so the MIT search tool imports nothing from the AGPL-3.0 `detector/` folder:

~~~
python -m venv detector-venv
detector-venv/bin/pip install ultralytics==8.4.218
python probe/open_water_search.py flight.mp4 --mode detector-check --detector-python detector-venv/bin/python --out results --budget 0.10
~~~

The detector downloads its pinned weights on first use and runs on the Apple GPU by default. Pass `--detector-device cpu`, or a CUDA device number, elsewhere. It keeps swimmer boxes at 0.05 confidence or more, at most 12 per frame, and Ember gets one request per frame that has any. The tool prints Ember's verdict on each flag in its own words as the answers arrive. Kept flags become sightings, and they merge into possible people the same way. Each handoff message quotes what Ember said and how many of that frame's flags it kept and dismissed. The report lists every dismissed flag with its crop, so a reviewer can reopen it, and `detector-boxes.json` holds every box the detector returned. The detector runs before any Ember call, so a missing ultralytics stops the run before it spends anything. On the 300 MOBDrone frames, the check cost about $0.0001 per frame.

Add `--mode agent` to let Ember run the search through tool calls. Each frame gets one conversation that opens with its overview and a one-line note about the previous frame's sightings. Ember chooses which tiles to look at closely, at most 4 per frame, reports each sighting as a point on Meta's 0–1,000 grid over the close look it received, and moves to the next frame when it decides to. Each frame earns an equal share of `--budget`, and any share it leaves unused carries forward. The tool prints a line for each tool call as it happens. It lost to the fixed method on the 30 validation photos, so the fixed method stays the default.

| File in `results/` | What it holds |
|---|---|
| `search-record.json` | The search record: every possible sighting in source-image pixels, the possible people they merge into with a handoff message for each, the coverage timeline with every section's status for every second, every Ember call with its tokens and cost, and how the run ended |
| `report.html` | The reviewer queue, highest confidence first, and a coverage map of every frame, built from the search record |
| `queue.json` | Up to five sightings per frame, in source-image pixels, built from the search record |
| `coverage.json` | Every section's status for every frame, from the search record |
| `calls.jsonl` | Every Ember request, with its token usage, cost and answer |
| `detector-boxes.json` | In `--mode detector-check`, every box the detector returned for every frame |

With the default grounding format, an overview plus two close looks cost about $0.00062 per photo on the scale run, or about $2.23 per hour of footage at one photo a second. The search record also records photos per minute.

## The three web pages

| Page | What you do there |
|---|---|
| [How it works](https://open-water-search.vercel.app) (`pages/index.html`) | Watch the live two-minute run print Ember's decisions and fill in its coverage timeline, read the handoff message for each possible person, then see the scale run, the detector comparison and the steps on one real validation photo |
| [Recorded flight handoff](https://open-water-search.vercel.app/judge) | Open the last reported pin, download its self-contained crew packet and inspect an earlier dismissal of the same swimmer. |
| [Earlier zoom experiment](https://open-water-search.vercel.app/pages/judge.html?run=validation) (`pages/judge.html`) | Ember has taken one overview, opened its top tile and flagged a possible swimmer. You mark it, dismiss it or say you can't tell. Then you pick the next tile, see Ember's recorded close look there, and reveal the labels. |
| [Replay](https://open-water-search.vercel.app/replay) (`pages/replay.html`) | Put Ember and the fixed grid side by side on every frame of either run, at 1 to 9 close looks per frame, with spend and totals across all 30 frames |

The take-over page works like this:

~~~mermaid
stateDiagram-v2
    state "Ember flagged a tile" as flag
    state "Look at Ember's close look" as crop
    state "Pin the swimmer on the full photo" as pin
    state "Pick the next tile" as pick
    state "See Ember's look at your tile" as next
    state "What was there" as reveal
    [*] --> flag
    flag --> crop: Open Ember's close look
    crop --> pin: Mark a swimmer
    crop --> pick: Dismiss the flag / Can't tell
    pin --> crop: Back (keeps your pin)
    pin --> pick: Lock my pin
    pick --> next: Open this tile
    next --> reveal: Reveal the labels
    reveal --> flag: Try another search / Start this one over
~~~

The reveal shows whether the flag was real, where your pin landed, what your pick held, what Ember would have opened next, and how many swimmers remain in water nobody has checked. Cases follow manifest order and include every validation frame whose first close look flagged something and which has a swimmer outside that tile. The replay page's totals at nine looks match `score.json`, and at one to three looks they match the order table.

To run the pages locally:

~~~
pip install pillow
python probe/fetch_frames.py
python -m http.server 8000
~~~

Then open `http://localhost:8000/pages/index.html`. `probe/build_pages.py` rebuilds `pages/runs/` from the sealed traces and from `runs/live-clip`, and reads no labels. The pages load labels in the browser from the files `fetch_frames.py` downloads.

The hosted site comes from `python probe/build_site.py`, which copies the pages, the run data, and the frames resized to 2,400 pixels, along with their labels, into `site/`. Then `vercel deploy site --prod` publishes it. SeaDronesSee is CC0, so the site can carry frames and labels that this repository leaves out.

## Reproduce the numbers

~~~
pip install pillow
python probe/fetch_frames.py      # downloads the 60 frames and labels from the pinned mirror and checks every hash
python probe/check.py             # offline checks with simulated answers, no API calls
python -m unittest discover -s probe  # the command end to end against a simulated Ember, no API calls
python probe/score.py             # rebuilds the first-run scorecards and compares them with experiments/zoom-first/training-30/live/
python probe/score.py validation  # the same for experiments/zoom-first/validation-30/live/
~~~

The order tables are under `order_table` in each `score.json`. `score.py` refuses to score unless the trace matches its seal.

`python probe/score.py record SEARCH_RECORD SCORING_DIR` prints the scorecard for a search record under the same rule, and `python probe/score.py detector BOXES_JSON SCORING_DIR` does the same for the detector's boxes. Each folder under `runs/` keeps its published scorecard and the seal of its search record and calls log. `detector/README.md` has the detector's commands.

To make your own sealed run on macOS, move `experiments/zoom-first/training-30/live/` or `experiments/zoom-first/validation-30/live/` aside. Then, with `MODEL_API_KEY` set, run `sh probe/isolate.sh runner.py --dataset probe --prior-nanodollars 0` from the repository root. The launcher uses `sandbox-exec` so the inference process cannot read the label folders. The runner caps a run at $0.49, reserves each request's worst-case cost before sending it, and stops after ten unreadable answers in a row. After a 429 rate-limit reply, it waits once and retries once, as Meta's rate-limit guidance asks.

## What is and isn't here

The traces are Ember's replies as returned, minus Meta's response and message IDs. `redaction.json` gives the SHA-256 of each original trace, which matches its `seal.json`, and of the redacted copy. No API key is stored anywhere in the repository. The SeaDronesSee images and labels are not included. `fetch_frames.py` downloads them from the mirror at revision `deb1f872` and checks each one against the SHA-256 recorded in the manifests. `docs/` holds a screenshot of the landing page, the search steps on one validation frame, and the five MOBDrone crops of the detector-check result.

The MOBDrone videos, frames and labels are not included either, apart from the five 224-pixel crops in `docs/ember-check-examples.png`, credited to MOBDrone's authors under CC BY 4.0. `mobdrone/frames.json` lists the 300 frames of unseen footage, by video, frame number and time, with the SHA-256 of each of the 66 source videos. `select_mobdrone.py` chose them from video names and frame counts alone, with a fixed seed, and the list was committed before any frame or label was viewed. `python probe/fetch_mobdrone.py DATA_DIR` downloads the videos and the people-only labels from Zenodo, checks them against Zenodo's MD5 and the recorded SHA-256, unpacks the videos into `DATA_DIR/videos`, and checks that the label file has an entry for every frame of every video, the 300 chosen ones included.

`python probe/extract_mobdrone.py DATA_DIR SAMPLE_DIR` then takes each of the 300 frames by its frame number and saves it in `SAMPLE_DIR/images` under a name that keeps the list's order, so the folder searches as a flight. It converts the frame's person boxes into a YOLO label file with class 0, the class scored as a swimmer, and writes `mobdrone/inputs/manifest.json` and `mobdrone/scoring-only/manifest.json` with the SHA-256 of every photo and label. `probe/cut_mobdrone_clip.py` cuts the two-minute clip for the live run and labels each second the search tool will cut from it, with MOBDrone's track IDs. `probe/check_merge_rule.py SEARCH_RECORD SCORING_DIR` counts how often the possible-person merge rule joined two different labeled people and how often it split one.
