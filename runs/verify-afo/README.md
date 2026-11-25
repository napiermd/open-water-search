# Detector, then Ember on AFO: results

The plan in `PLAN.md` was committed (1a34171) before any Ember call. Run on November 24, 2026, with muse-ember-1.0. It cost $0.0706 for 255 requests, one per photo with at least one flag, under a $0.10 cap. It finished without stopping early.

**Photos.** 300 photos from the test split of AFO (Gąsienica-Józkowy, Knapik and Cyganek, 2021; CC BY-NC-SA 3.0, used non-commercially), across all 17 of its source clips, holding 2,950 labelled person appearances. The detector was trained on SeaDronesSee and never saw AFO. AFO frames are crowded, so under the scoring rule's five marks per photo at most 874 of the 2,950 can be found by anyone.

| | Found | False alarms |
|---|---|---|
| Detector, then Ember | 619 | 85 (75 on water or objects with no labelled person, 10 second marks) |
| Detector alone at 0.05, its most sensitive setting | 611 | 445 |
| Detector alone at 0.25, as published | 556 | 310 |
| Detector alone at 0.60, with about as many false alarms as Ember's check | 217 | 83 |

**Against the pass rule: it does not apply as written.** The rule compares Ember's check with the detector at the highest confidence that still finds at least as many people. Ember's check found 619, and the detector alone finds at most 611 at any confidence, so no such setting exists. The rule did not anticipate the check finding more people than the detector can.

**After the result, and not part of the plan:** against the detector's most sensitive setting, Ember's check found 8 more people with 360 fewer false alarms, 81% fewer. Against the published setting, it found 63 more people with 225 fewer false alarms. Ember finds more because the scoring keeps five marks per photo: once it drops the false flags, more of the five land on people.

**What Ember did with the 1,951 flags.** It kept 991 of the 1,101 flags on labelled people and dismissed 768 of the 850 that were not. In its own words, the dismissed non-people were mostly seaweed, rocks and people standing on land rather than in the water. Of the 110 real people it dismissed, it often described the crop's centre as open water between two swimmers: in crowded groups the crop centred on a gap.

`comparison.json` holds the detector's full trade-off from 0.05 to 0.95. `seal.json` holds the SHA-256 of `checks.jsonl` as written. The published `checks-redacted.jsonl` has Meta's response and message IDs removed. AFO's photos and labels are not in the repository.
