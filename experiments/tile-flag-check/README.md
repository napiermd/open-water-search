# Ember kept the paddler and added 80 false-alarm episodes

At second 37 of `DJI_0804_0012_50m_3`, the current Muse Ember check accepted the tiled swimmer flag for track 8. Its exact description was “person on paddleboard” and its reported confidence was 0.95. This was the only additional labelled track found on these seven known clips.

| Across the same 254 pilot frames | Existing check | With checked tile additions | Change |
|---|---:|---:|---:|
| Labelled track IDs found / 35 | 32 | 33 | +1 |
| Person-seconds marked / 231 | 160 | 177 | +17 |
| False marks | 42 | 155 | +113 |
| Seconds with a false mark | 35 | 80 | +45 |
| False-alarm episodes | 26 | 106 | +80 |

Of 1,349 tiled flags, 301 overlapped an original flag under the frozen 0.50 intersection-over-union rule. Ember checked the remaining 1,048 flags and kept 170. Of these, 57 landed on labelled people and 113 landed outside every person box. Scored alone, those new false marks formed 87 episodes. Rebuilding the combined record under the original episode-linking rule raised the total by 80. These are recorded false-alarm episodes; human interruptions and response time were not measured.

All 172 requests to the personal Meta Model API returned usable results. Token charges totaled $0.040484640 under the approved $0.10 ceiling. The six reserve clips were outside the manifest. The production check stays as it was.

[Registered plan](PLAN.md) · [Per-clip results](summary.json) · [Ember verdicts](verdicts.jsonl) · [Request charges](charges.json) · [File hashes](seal.json)

## Offline replay of a stricter cutoff

A tile-only threshold of **Ember confidence ≥0.92** retained the second-37 paddler and removed **78 of the 80 added false-alarm episodes** on the same seven pilot clips. The original whole-frame decisions stayed fixed. Every cutoff was scored by rebuilding the combined search record and relinking false marks within each eligible stretch.

| Minimum confidence on tile yes answers | Paddler retained | Total episodes (26 at baseline) | Added false marks | Added correct person-seconds |
|---|---|---:|---:|---:|
| Any yes | Yes | 106 | 113 | 17 |
| 0.90 | Yes | 31 | 8 | 6 |
| 0.92 | Yes | 28 | 3 | 4 |
| 0.95 | Yes | 28 | 3 | 3 |
| 0.98 | No | 26 | 0 | 0 |

Both 0.92 and 0.95 reached the lowest extra episode count that still retained the target. At 0.92 the record kept one more correct person-second. The cutoff was selected on these known clips. It is a candidate for validation. Replay spend was $0. The six reserve clips were outside the replay, and production settings stayed fixed.

Run `python3 experiments/tile-flag-check/replay_cutoffs.py` with the original MOBDrone annotations to reproduce the [complete threshold sweep](cutoff-sweep.json). The script checks the source hashes and reproduces both the baseline and the unfiltered result before comparing thresholds.
