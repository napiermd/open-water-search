# Does padding edge crops find anyone new?

Both checks found the same seven of nine labelled people. Padding added three correct sightings of people already found and one net false-alarm episode. The 0.65 edge rule and the footage selection method were [locked before inspection](https://github.com/napiermd/open-water-search/blob/a672f12/experiments/fresh-edge-065/PLAN.md).

| Across 86 sampled seconds from eight clips | Current Ember check | Padded edges at 0.65 |
|---|---:|---:|
| People found / eligible | 7/9 | 7/9 |
| Correctly marked person-seconds / eligible | 54/64 | 57/64 |
| Individual false marks | 31 | 32 |
| Seconds containing a false mark | 8 | 10 |
| False-alarm episodes after linking nearby marks over time | 25 | 26 |

Track numbers identify people within a clip. The table lists seconds with at least one correct mark.

| MOBDrone clip (short ID) | Track | Current check | Padded edges |
|---|---:|---|---|
| 0004 | 1 | 27–36 | 27–36 |
| 0005 | 0 | 24–32, 34 | 24–32, 34 |
| 0005 | 1 | Missed 32–34 | Missed 32–34 |
| 0008 | 1 | 0–3 | 0–3 |
| 0011 | 0 | 16–26 | 15–26 |
| 0013 | 3 | 64–67 | 64–67 |
| 0014 | 3 | Missed 54–56 | Missed 54–56 |
| 0022 | 1 | 53–59 | 53–60 |
| 0031 | 3 | 42–49 | 42–50 |

The detector put a pin inside each missed person's labelled box on all three seconds they were visible. In 0005, Ember rejected all three flags in both policies. In 0014 at second 54, the original answer described buoy equipment. With padding Ember answered yes and described a “dark swimmer with white fins” at 0.60 confidence. The locked policy filtered it out. Both checks rejected the next two flags.

These were fresh windows chosen for edge flags using detector boxes alone. The eight source families were outside the earlier pilot and reserve sets. Previous still-image experiments had sampled other times in these recordings. The result describes footage selected to exercise the edge rule.

Personal Meta API, muse-ember-1.0. Both checks together used 144 successful requests costing $0.025493388 against a $0.05 cap. All 86 seconds had complete paired results. The current check evaluated 514 flags, and 80 edge flags received a padded recheck. Other flags shared the original verdict.

[Per-track scores](summary.json) · [Saved verdicts](verdicts.jsonl) · [Per-request charges](charges.json) · [File hashes](seal.json)
