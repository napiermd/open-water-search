# Live run: a two-minute MOBDrone clip

Ticket #16. The command ran on a 120-second clip of MOBDrone video DJI_0915_0007_40 (frames 1682–5278), chosen from labels alone as described in the project notes. It searched one frame per second with the default fixed method, at most 8 requests at once, on November 24, 2026:

```
python3 probe/open_water_search.py clip.mp4 --out runs/live-clip --budget 0.10
```

`terminal.jsonl` is everything the command printed, each line with its time in seconds from the start: one line per overview and close look as its answer arrived, then the handoff message for each possible person.

| Result | Value |
|---|---|
| Seconds of footage | 120 |
| Person appearances found | 107 of 116 (92%) |
| Marks with no person | 47 |
| Possible people | 15, for 4 labeled people |
| Cost | $0.0531 |
| Photos per minute | 46.9 (wall time 153.6 s, including cutting the video) |

**Merge rule, checked with `probe/check_merge_rule.py` against MOBDrone's track IDs:**

- It never joined two different people.
- All 4 labeled people were split into more than one possible person: 6 splits, all within two seconds.
- 7 of the 15 possible people hold no labeled person. MOBDrone labels only people, so some may be boats or buoys, and the rest are false sightings.

`seal.json` holds the SHA-256 of the search record and calls log as written. The published copies have Meta's response and message IDs removed. MOBDrone is by Cafarelli et al. (arXiv 2203.07973), CC BY 4.0.
