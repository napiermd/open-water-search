# Live run: the one command, detector then Ember, on the two-minute MOBDrone clip

Approved by Andrew with a $0.05 cap. The command ran on November 24, 2026, from commit b073698 on main, on the same 120-second clip of MOBDrone video DJI_0915_0007_40 (frames 1682–5278) as `runs/live-clip`. It was run from the folder holding the clip, so its paths reach back into the repository:

~~~
python3 -u ../../repo/open-water-search/probe/open_water_search.py clip.mp4 --mode detector-check --detector-python ../../work/detector-venv/bin/python --out ../../repo/open-water-search/runs/live-detector-check --budget 0.05 --key-file KEY_FILE
~~~

`terminal.jsonl` is everything the command printed, each line with its time in seconds from the start: the detector's count, Ember's verdict on every flag in its own words as each answer arrived, then the handoff message for each possible person.

| Result | Value |
|---|---|
| Seconds of footage | 120 |
| Detector flags | 115 in 99 of the 120 frames |
| Person appearances found | 105 of 116 (91%) |
| False alarms | 0 |
| Possible people | 6, for 4 labeled people, each holding a labeled person |
| Cost | $0.0081 for 99 Ember requests |
| Time | 192 s from start to finish, including cutting the video and 16 s for the detector |

**On this clip the detector alone did better.** Scored from `detector-boxes.json` under the same rule, the detector at its published 0.25 confidence found 114 appearances with 1 false alarm. Ember's check removed that one false alarm and dismissed 9 real sightings: six it called a bird, a duck or a seal, and three it described as a person away from the centre of the crop. To find as few as 105, the detector's own threshold can rise to 0.68 with 0 false alarms. On this footage the detector was already clean, so the check had nothing to add. The 300-frame test in `runs/verify-mobdrone`, where the detector raised 166 false alarms, is where the check paid off.

**The handoff is cleaner than Ember's own search on the same clip** (`runs/live-clip`: 107 found, 47 marks with no person, 15 possible people of which 7 held no labeled person, $0.0531). `probe/check_merge_rule.py` found that the merge rule never joined two different people here. It split two of the four labeled people, each after a gap of more than two seconds (`merge-rule-check.json`).

`seal.json` holds the SHA-256 of the search record and calls log as written. The published copies have Meta's response and message IDs removed. `scorecard.json` is `probe/score.py record` against the clip's labels. MOBDrone is by Cafarelli et al. (arXiv 2203.07973), CC BY 4.0.
