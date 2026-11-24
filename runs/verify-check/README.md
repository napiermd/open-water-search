# Detector, then Ember: results

The plan in `PLAN.md` was committed (f69027e) before any Ember call. Runs on November 24, 2026, muse-ember-1.0, $0.0391 in total.

| | Detector alone, as published | Detector, then Ember |
|---|---|---|
| MOBDrone, 300 frames, 311 people | 228 found, 194 false marks | 218 found, 45 false marks ($0.0336, 213 requests) |
| Validation, 30 photos, 134 swimmers | 86 found, 3 false marks | 78 found, 6 false marks ($0.0055, 25 requests) |
| **Both** | **314 found, 197 false marks** | **296 found, 51 false marks** |

**Against the pass rule: not passed.** It needed at least 314 found with fewer than 197 false marks. It found 18 fewer people.

**After the result, and not part of the plan:** the detector's own trade-off between people found and false marks, from the same 0.05-confidence candidates, with the top five per photo kept:

| Detector confidence | Found | False marks |
|---|---|---|
| 0.05 (every candidate) | 336 | 299 |
| 0.25 (published) | 314 | 197 |
| 0.35 | 296 | 171 |
| 0.60 | 193 | 72 |
| 0.65 | 166 | 37 |

At 296 found, the detector alone makes 171 false marks, and Ember's check makes 51. At about 51 false marks, the detector alone finds between 166 and 193. This comparison was chosen after the result was seen, on 330 photos, so it needs its own pre-registered test on new photos before it can be claimed.

`seal.json` in each folder holds the SHA-256 of `checks.jsonl` as written. The published `checks-redacted.jsonl` has Meta's response and message IDs removed.
