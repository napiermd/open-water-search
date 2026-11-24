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

**First take.** The same command, run earlier from the folder holding the clip, is in `runs/live-detector-check-first-take`: 105 found, no false alarms, 6 possible people, $0.0081, 192 s. The detector's flags were the same. Ember's answers differ between runs, and so did Meta's response times.

`seal.json` holds the SHA-256 of the search record and calls log as written. The published copies have Meta's response and message IDs removed. `scorecard.json` is `probe/score.py record` against the clip's labels. MOBDrone is by Cafarelli et al. (arXiv 2203.07973), CC BY 4.0.
