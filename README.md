# Open Water Search

**A trained detector flags every second of a drone flight. Muse Ember checks each flag, says what it is, and the crew gets a search record built from what Ember kept.**

[![Tests](https://github.com/napiermd/open-water-search/actions/workflows/tests.yml/badge.svg)](https://github.com/napiermd/open-water-search/actions/workflows/tests.yml) · [Website](https://open-water-search.vercel.app) · Built during the Muse Ember Hackathon, starting November 23, 2026.

On two drone datasets the detector never saw, Ember's check found at least as many people with far fewer false alarms:

| Footage the detector never saw | Detector, then Ember | Detector alone |
|---|---|---|
| [MOBDrone](runs/verify-mobdrone/README.md), 300 frames, 297 people | **210 found, 38 false alarms** | 210 found, 166 false alarms |
| [AFO](runs/verify-afo/README.md), 300 photos, 2,950 people | **619 found, 85 false alarms** | at most 611 found at any setting, with 445 false alarms |

Each pass rule was committed before its run, and the runs cost $0.0318 and $0.0706. AFO's rule compared Ember's check with the detector at the setting that finds as many people, and no setting does, so the rule could not be applied as written. The AFO comparison above was chosen after the result was seen.

![Five detector flags. Ember dismissed a rock, driftwood and a life ring, kept a person floating on their back, and wrongly called a swimmer a seagull](docs/ember-check-examples.png)

## How it works

~~~mermaid
flowchart LR
    flight["Flight: video or photos,<br/>one per second"] --> detector["Trained detector<br/>flags up to 12 spots a frame"]
    detector --> ember["Muse Ember<br/>one request per flagged frame:<br/>person? how sure? what is it?"]
    ember -->|kept| record["Search record<br/>possible people in Ember's words,<br/>a handoff message for each"]
    ember -->|dismissed| reopen["Dismissed flags<br/>listed for a person to reopen"]
~~~

The detector is a free YOLO26m model trained on SeaDronesSee. It runs on this machine and flags every swimmer-shaped spot at 0.05 confidence or more. Ember gets one request per flagged frame, with each flag as a numbered 224-pixel crop. Structured output makes it answer three questions for every crop: is a person in the water at its centre, how sure is it, and what is there. Before each request, the tool counts its input tokens and reserves the worst-case cost, so a run stops before it can cross its spending cap.

## Run it

~~~
pip install -r requirements.txt
python -m venv detector-venv && detector-venv/bin/pip install -r detector/requirements.txt
export MODEL_API_KEY=your-meta-model-api-key
python probe/open_water_search.py flight.mp4 --mode detector-check --detector-python detector-venv/bin/python --out results --budget 0.10
open results/report.html
~~~

A flight is a video, cut into one frame per second with ffmpeg, or a folder of photos one second apart. You get a search record of possible people with a handoff message for each, a report page that lists every kept flag and every dismissed one, and every Ember call with its cost. On a live two-minute clip the command ran in 57 seconds for $0.0080 ([runs/live-detector-check](runs/live-detector-check/README.md)). Without `--mode detector-check`, Ember searches each frame alone and needs no detector. Every option is in [docs/reproduce.md](docs/reproduce.md).

## What it doesn't show

- **On the detector's own footage it loses.** On 1,517 SeaDronesSee photos, Ember's check made 291 false alarms where raising the detector's threshold made 104 at the same people found ([runs/verify-confirm](runs/verify-confirm/README.md)). The check earns its keep on water the detector doesn't know.
- **It dismisses real people.** It turned down 40 on MOBDrone and 110 on AFO, calling some a bird or the water between two swimmers. Two revised prompts aimed at this both dismissed more people, not fewer, so the original stays ([runs/prompt-revision](runs/prompt-revision/README.md)). The report keeps every dismissed flag for a person to reopen.
- **On an easy clip it adds nothing.** On the live clip the detector alone found 114 of 116 with one false alarm, and the check found 101 with none.
- **Two datasets are not every sea.** Footage beyond MOBDrone and AFO is untested, and there is no claim that a reviewer finds people faster.

## Where things are

| Path | What it holds |
|---|---|
| `probe/` | The search command (`open_water_search.py`), Ember's check, the scorer and their offline tests |
| `detector/` | The trained detector and its runs, under AGPL-3.0 |
| `runs/` | Every paid run, sealed: its plan, results, redacted Ember calls and cost |
| `pages/` | The website: the result, a search you can take over, and a replay |
| `docs/` | [Results](docs/results.md) in full, [run and reproduce](docs/reproduce.md), [history](docs/history.md), the [glossary](docs/GLOSSARY.md) and every [decision record](docs/adr) |
| `experiments/zoom-first/` | The first day's experiment, where Ember searched alone |

**How we decided.** Each paid test had its plan and pass rule committed before its first Ember call, and the ones that failed are published next to the ones that passed. The decision records show every turn, including the reversal that made the detector the first pass ([ADR 0016](docs/adr/0016-the-detector-makes-the-first-pass.md)). New Ember spending since November 24 is capped at $3.00 in total, and every run's cost is in its folder.

## Credits and license

Code: MIT, except `detector/`, which is AGPL-3.0 because the detector library and checkpoint are. The search tool runs the detector as a separate program and imports nothing from it.

Footage: SeaDronesSee (Varga, Kiefer, Messmer and Zell; CC0), MOBDrone (Cafarelli et al.; CC BY 4.0), and AFO (Gąsienica-Józkowy, Knapik and Cyganek; CC BY-NC-SA 3.0, used non-commercially). No dataset images are in this repository apart from the five MOBDrone crops above, credited under CC BY 4.0. Download scripts and hashes are in [docs/reproduce.md](docs/reproduce.md).
