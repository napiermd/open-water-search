# Live run: the one command, detector then Ember, on the two-minute MOBDrone clip

Approved by Andrew with a $0.05 cap. The command ran on November 24, 2026, from the repository folder on main, on the same 120-second clip of MOBDrone video DJI_0915_0007_40 (frames 1682–5278) as `runs/live-clip`. `clip.mp4` and `detector-venv` are local links to the clip and to a Python with ultralytics, and the key came from `MODEL_API_KEY`:

~~~
python3 -u probe/open_water_search.py clip.mp4 --mode detector-check --detector-python detector-venv/bin/python --out runs/live-detector-check --budget 0.05
~~~

`terminal.jsonl` is everything the command printed, each line with its time in seconds from the start: the detector's count, Ember's verdict on every flag in its own words as each answer arrived, then the handoff message for each possible person. This is the recording for the video.

| Result | Value |
|---|---|
| Seconds of footage | 120 |
| Detector flags | 115 in 99 of the 120 frames |
| Person appearances found | 101 of 116 (87%) |
| False alarms | 0 |
| Possible people | 8, for 4 labeled people, each holding a labeled person |
| Cost | $0.0080 for 99 Ember requests |
| Time | 57 s from start to finish, including cutting the video and 8 s for the detector: faster than the footage plays |

**On this clip the detector alone did better.** Its boxes were identical to the first take's. Scored under the same rule, the detector at its published 0.25 confidence found 114 appearances with 1 false alarm, and at 0.69 it finds 102 with none. Ember's check dismissed 13 real sightings: eight it called a duck, a bird, a seal or a dolphin, four it described as a person away from the centre of the crop or at its edge, and one a dark floating shape. On this footage the detector was already clean, so the check had nothing to add. The 300-frame test in `runs/verify-mobdrone`, where the detector raised 166 false alarms, is where the check paid off.

**The handoff is cleaner than Ember's own search on the same clip** (`runs/live-clip`: 107 found, 47 marks with no person, 15 possible people of which 7 held no labeled person, $0.0531). `probe/check_merge_rule.py` found that the merge rule never joined two different people here. It split two of the four labeled people, four times in all, three of them after a gap of more than two seconds (`merge-rule-check.json`).

**First take.** The [earlier run](../live-detector-check-first-take/README.md) used the same command from the folder holding the clip. It found 105 appearances with no false alarms and returned 6 possible people. It cost $0.0081 and took 192 seconds. The detector's flags were the same. Ember's answers and Meta's response times differed between runs.

`seal.json` holds the SHA-256 of the search record and calls log as written. The published copies have Meta's response and message IDs removed. `scorecard.json` is `probe/score.py record` against the clip's labels. MOBDrone is by Cafarelli et al. (arXiv 2203.07973), CC BY 4.0.

## Offline flight replay

The [sealed replacement test](../../experiments/lost-people/sealed-off-center/result.json) restored zero pins. Both variants found 2 of 2 people with one false pin in one episode, so the current detector check is the selected policy.

From the repository root, use the original local clip and a new output path. Byte-for-byte reproduction was verified on macOS with Python 3.14.7, Pillow 13.0.0, libjpeg-turbo 3.2.0, ffmpeg 8.1.1 and LF line endings. Different encoders or Windows CRLF line endings can fail the byte checks. Windows reproduction is unverified.

```sh
python runs/live-detector-check/replay_flight.py /path/to/clip.mp4 results/offline-flight
open results/offline-flight/report.html
```

The replay calls the normal `detector-check` entry point with the sealed boxes and redacted Muse Ember 1.0 replies. It extracts the 120 frames from the video, checks their hashes, and matches all 99 requests to the saved replies. Request hashes were reconstructed from the sealed frames and boxes. Python connections are refused during the run. A fresh detector pass is unnecessary. The command preserves the original token usage and displays the historical $0.0080 charge. The replay makes zero external model calls and incurs $0.

| Generated evidence | Verified result |
|---|---|
| `queue.json`, `coverage.json`, `detector-boxes.json` | Byte-for-byte match to the [published queue](queue.json), [coverage](coverage.json) and [boxes](detector-boxes.json) |
| `report.html` | 101 queue entries across 120 seconds. Every one of the 115 flag crops links to its source frame and matches the corresponding request JPEG. |
| `search-record.json` and terminal output | The [web replay](../../pages/runs/live-detector-check.json) matches the saved flag statuses across all 120 timeline cells and the text and source second of all 99 verdicts. All eight handoff messages, numbers, first and last seconds, and labeled-person IDs match the saved record and [merge-rule check](merge-rule-check.json). |
| `probe/score.py record` with the original local labels | Exact match to the [published scorecard](scorecard.json), with 101 of 116 person appearances found and zero false marks |

Follow queue rank 66 to `report.html#second-00022` and `crops/second-00022-flag1.jpg`. The coverage entry records the detector box `[693.35, 335.74, 752.07, 380.42]`. The queue pin is at `(722.7, 358.1)` in source-frame pixels. Possible person 1 was first seen at 0:08 and last seen at 0:22, in the center of `second-00022`. The handoff quotes Ember’s “person floating on water” and reports one kept flag and zero dismissed flags in that frame.

At 0:06, Ember's “person floating right of centre” remains dismissed. Its crop is available in the report and its pin stays out of the reviewer queue.
