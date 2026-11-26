# Open Water Search

**A trained detector flags every second of a drone flight. Muse Ember checks each flag, says what it is, and the crew gets a search record built from what Ember kept.**

[![Tests](https://github.com/napiermd/open-water-search/actions/workflows/tests.yml/badge.svg)](https://github.com/napiermd/open-water-search/actions/workflows/tests.yml) · [Open the recorded flight](https://open-water-search.vercel.app) · Built during the Muse Ember Hackathon, starting November 23, 2026.

## What reaches the crew in the first five handoffs?

On all 129 eligible 24-second MOBDrone windows, checking swimmer flags with Muse Ember reduced empty handoffs from **176 to 113**, or **35.8% fewer** (95% interval **26.7% to 46.4%**). The reviewer opens up to five cards per window. Both queues use the same ranking.

| Queue | Swimmer tracks reached / 258 | Repeat pins | Empty handoffs | Change in reach, percentage points (95% interval) | Fewer empty handoffs (95% interval) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ranked detector | 201 | 53 | 176 | Reference | Reference |
| Detector + Ember checking swimmer flags | 212 | 86 | 113 | +4.3 (−0.4 to +8.7) | 35.8% (26.7% to 46.4%) |
| Detector + Ember checking swimmer and boat flags | 215 | 86 | 116 | +5.4 (+0.5 to +10.0) | 34.1% (24.5% to 44.7%) |

A track counts once per window. A person can appear in several windows. The swimmer-only check brought 19 tracks into the first five and displaced 8 the detector reached. Its interval for reach includes zero. The intervals come from 20,000 paired draws of the 42 recording families. Some footage also informed development. Crew response time remains unmeasured. [Per-window scores](experiments/first-five/archive-129/windows.csv) · [Interval estimates](experiments/first-five/archive-129/intervals.json).

**See where the ranking matters.** In a separate Cyprus Civil Defence exercise, the swimmer ranked eighth in the detector queue and first after Ember checked the crops. Open the two matching pins and any of the seven detector cards ahead of the swimmer. [Replay Cyprus](https://open-water-search.vercel.app/pages/cyprus.html) · [Open the recorded crew handoff](https://open-water-search.vercel.app/judge).

## Separate still-photo benchmarks

On two drone datasets the detector never saw, Ember's check found at least as many people with far fewer false alarms:

| Footage the detector never saw | Detector, then Ember | Detector alone |
|---|---|---|
| [MOBDrone](runs/verify-mobdrone/README.md), 300 frames, 297 labeled person appearances | **210 found, 38 false alarms** | 210 found, 166 false alarms |
| [AFO](runs/verify-afo/README.md), 300 photos, 2,950 labeled person appearances | **619 found, 85 false alarms** | at most 611 found at any setting, with 445 false alarms |

Each pass rule was committed before its run, and the runs cost $0.0318 and $0.0706. AFO's rule compared Ember's check with the detector at the setting that finds as many people, and no setting does, so the rule could not be applied as written. The AFO comparison above was chosen after the result was seen.

![Five detector flags. Ember dismissed a rock, driftwood and a life ring, kept a person floating on their back, and wrongly called a swimmer a seagull](docs/ember-check-examples.png)

## Replay the detector check

The original 120-second MOBDrone run took 57 seconds and cost $0.0080. It returned 101 sightings and eight possible people for four labeled people. Select any of the eight to read the recorded handoff on the site. [Watch the replay and open the handoffs](https://open-water-search.vercel.app/pages/index.html#live-check-title).

To reproduce that run from the repository root, use the exact clip from `DJI_0915_0007_40.mp4`, starting at source frame 1682. The repository includes the [clip cutter](probe/cut_mobdrone_clip.py) and the [manifest with the clip hash and frame list](mobdrone/clip/scoring-only/manifest.json). The [replay instructions](runs/live-detector-check/README.md#offline-flight-replay) list the verified tool versions.

~~~sh
python runs/live-detector-check/replay_flight.py /path/to/clip.mp4 results/offline-flight
open results/offline-flight/report.html
python probe/export_handoff.py results/offline-flight 1 --out handoff-1.html
~~~

The normal detector-check command replays the saved detector boxes and all 99 Muse Ember replies for $0 in new charges. The reviewer queue and coverage match the original byte for byte. The replay verifies all eight handoffs and 115 crop links. For possible person 1, follow queue rank 66 to `report.html#second-00022` and `crops/second-00022-flag1.jpg`. The handoff ends at 0:22 and quotes Ember's “person floating on water.” The [run record](runs/live-detector-check/README.md#offline-flight-replay) gives the exact pin and crop provenance.

## Why the current check stays

We tested a rule that would restore the original detector pin when Ember dismissed it but described a person away from the crop's center.

- **Two sealed replacement clips.** The gate required at least one correctly restored pin and zero added false pins. The rule never fired. Both versions found 2 of 2 distinct tracks, with 20 correct original pins and 1 false pin in 1 episode. The rule added 0 correct pins and 0 false pins, so the current detector check stays. Replaying this test requires coordinator-held local inputs. [Sealed result](experiments/lost-people/sealed-off-center/result.json) · [Replay requirements](experiments/lost-people/sealed-off-center/README.md).
- **Eight exploratory clips.** The current check found 6 of 7 distinct tracks with 29 false pins in 14 episodes. In a retrospective replay, the rule restored 4 correct pins and added 0 false pins. It reached 7 of 7 with the same false-pin and episode counts. The current check still misses one person in clip 0011 (`DJI_0804_0011_30m_2`), where it dismissed three matching detector pins at seconds 11–13.

## How it works

~~~mermaid
flowchart LR
    flight["Flight: video or photos,<br/>one per second"] --> detector["Trained detector<br/>flags up to 12 spots a frame"]
    detector --> ember["Muse Ember<br/>one request per flagged frame:<br/>person? how sure? what is it?"]
    ember -->|kept| record["Search record<br/>possible people in Ember's words,<br/>a handoff message for each"]
    ember -->|dismissed| reopen["Dismissed flags<br/>listed for a person to reopen"]
~~~

The detector is a free YOLO26m model trained on SeaDronesSee. It runs on this machine and flags every swimmer-shaped spot at 0.05 confidence or more. Ember gets one request per flagged frame, with each flag as a numbered 224-pixel crop. Structured output makes it answer three questions for every crop: is a person in the water at its centre, how sure is it, and what is there. The tool uses input-token counts to reserve estimated costs against a local run budget. Billed retries can affect account usage.

## Run it

~~~
pip install -r requirements.txt
python -m venv detector-venv && detector-venv/bin/pip install -r detector/requirements.txt
export MODEL_API_KEY=your-meta-model-api-key
python probe/open_water_search.py flight.mp4 --mode detector-check --detector-python detector-venv/bin/python --out results --budget 0.10
open results/report.html
~~~

A flight is a video, cut into one frame per second with ffmpeg, or a folder of photos one second apart. You get a search record of possible people with a handoff message for each, a report page that lists every kept flag and every dismissed one, and every Ember call with its cost. Without `--mode detector-check`, Ember searches each frame alone and needs no detector. Every option is in [docs/reproduce.md](docs/reproduce.md).

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
| `runs/` | Published comparison runs with results and available redacted Ember traces and costs |
| `pages/` | The website: the result, a search you can take over, and a replay |
| `docs/` | [Results](docs/results.md) in full, [run and reproduce](docs/reproduce.md), [history](docs/history.md), the [glossary](docs/GLOSSARY.md) and every [decision record](docs/adr) |
| `experiments/zoom-first/` | The first day's experiment, where Ember searched alone |

**How we decided.** We committed the comparison plans and pass rules in advance. The public comparison records include passes and failures, and the decision records explain why the detector became the first pass ([ADR 0016](docs/adr/0016-the-detector-makes-the-first-pass.md)). The project budget for new Ember spending since November 24 is $6.00, raised from $3.00 on November 24. The sealed replacement inputs remain private.

## Credits and license

Code: MIT, except `detector/`, which is AGPL-3.0 because the detector library and checkpoint are. The search tool runs the detector as a separate program and imports nothing from it.

Footage: SeaDronesSee (Varga, Kiefer, Messmer and Zell; CC0), MOBDrone (Cafarelli et al.; CC BY 4.0), and AFO (Gąsienica-Józkowy, Knapik and Cyganek; CC BY-NC-SA 3.0, used non-commercially). No dataset images are in this repository apart from the five MOBDrone crops above, credited under CC BY 4.0. Download scripts and hashes are in [docs/reproduce.md](docs/reproduce.md).
