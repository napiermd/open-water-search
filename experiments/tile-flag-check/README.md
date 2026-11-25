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
