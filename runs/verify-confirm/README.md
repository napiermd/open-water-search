# Detector, then Ember: confirmation results

The plan in `PLAN.md` was committed (89e0107) before any Ember call. Run on November 24, 2026, with muse-ember-1.0. It cost $0.2690 for 1,251 requests, one per photo that had at least one candidate, under a $0.30 cap. It finished without stopping early.

**Photos.** The 1,517 SeaDronesSee validation photos left after removing the 30 earlier validation photos. They hold 6,072 labelled swimmer appearances.

| | Found | False marks |
|---|---|---|
| Detector, then Ember | 3,904 | 291 |
| Detector alone at 0.40, the highest confidence that still finds at least 3,904 | 3,910 | 104 |
| Detector alone at 0.25, as published | 4,197 | 141 |
| Detector alone at 0.06, with about as many false marks as Ember's check | 4,268 | 301 |

**Against the pass rule: failed.** Detector-then-Ember needed fewer than 104 false marks at 3,904 found. It made 291, so the measured reduction is −180%. On these photos, raising the detector's own confidence threshold removes false marks better than asking Ember to check each candidate.

The trade-off seen on 330 photos in `runs/verify-check` did not repeat here. That comparison was chosen after its result was seen, and this run was its test.

`comparison.json` holds the detector's full trade-off from 0.05 to 0.95. `seal.json` holds the SHA-256 of `checks.jsonl` as written. The published `checks-redacted.jsonl` has Meta's response and message IDs removed.
