# Detector, then Ember on new MOBDrone frames: results

The plan in `PLAN.md` was committed (82d5225) before any Ember call. Run on November 24, 2026, with muse-ember-1.0. It cost $0.0318 for 207 requests, one per frame with at least one candidate, under a $0.10 cap. It finished without stopping early.

**Frames.** 300 MOBDrone frames none of the earlier runs used, holding 297 labelled people. The detector was trained on SeaDronesSee and has never seen MOBDrone footage.

| | Found | False marks |
|---|---|---|
| Detector, then Ember | 210 | 38 |
| Detector alone at 0.30, the highest confidence that still finds at least 210 | 210 | 166 |
| Detector alone at 0.25, as published | 219 | 176 |
| Detector alone at 0.62, with about as many false marks as Ember's check | 125 | 36 |

**Against the pass rule: passed.** Detector-then-Ember needed fewer than 166 false marks at 210 found. It made 38, a measured reduction of 77%. To get down to about 38 false marks by raising its own threshold, the detector alone gives up 85 of the 210 people.

**What Ember said.** Ember described the detector's most confident false marks that it turned down as dark rocks, seaweed patches and floating debris. It also turned down 40 candidates that were real people, often calling them a dark shape, a bird or an animal. Of its 38 false marks, 20 are on water with no labelled person, and 18 are second marks on a person already found.

**Limits.** These frames come from the same 61 videos as the first MOBDrone test, at least two seconds from any frame used before. The result repeats on new moments of that footage. It does not show the result holds on other footage. On SeaDronesSee photos, the footage the detector was trained on, the same check lost to the detector's own threshold (`runs/verify-confirm`).

`comparison.json` holds the detector's full trade-off from 0.05 to 0.95. `seal.json` holds the SHA-256 of `checks.jsonl` as written. The published `checks-redacted.jsonl` has Meta's response and message IDs removed.
