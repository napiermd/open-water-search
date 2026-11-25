# Six-clip reserve result at the locked 0.92 tile cutoff

**Zero additional labelled tracks and zero additional false-alarm episodes.** Both methods found the same 23 of 24 clip-local track IDs. The 25 accepted tile marks all landed on labelled people already found by the current search. They filled in one additional person-second. A labelled person marked multiple times within one second contributes once to that coverage measure.

| Across all six clips | Current Ember check | With tile additions ≥0.92 | Difference |
|---|---:|---:|---:|
| Track IDs found | 23/24 | 23/24 | 0 |
| Marked person-seconds | 183/224 | 184/224 | +1 |
| False marks | 83 | 83 | 0 |
| Seconds with false marks | 48 | 48 | 0 |
| Linked false-alarm episodes | 52 | 52 | 0 |

The result covers all 267 eligible seconds. With the longest clip (`DJI_0915_0015_50m`) removed, both methods found 16/16 tracks and produced 14 false episodes. The extra second of coverage came from `DJI_0915_0027_50m`. These paired counts describe held-out stretches from previously sampled recordings. No confidence tuning or repeat takes were performed on the reserve set.

## The one miss

In `DJI_0915_0015_50m`, track 7 was labelled at the top image edge in seconds 135–139. An original candidate center landed in its box in four of those five seconds. Ember dismissed all four. At second 136 the flag was 8.66 pixels below the top of the image. Keeping the crop inside the picture moved the crop center to 48 pixels below the top. Ember returned “partial swimmer at top edge, centre empty water.” Its next two answers also described a person or figure at the edge. No additional tiled flag center landed on that track. The reserve result gives no evidence for promoting blanket tiling to the default search.

## Run record

The [protocol](https://github.com/napiermd/open-water-search/blob/661b5a8/experiments/reserve-092/PLAN.md) was committed and pushed before the reserve footage was opened. The [inputs and blinded exclusions](https://github.com/napiermd/open-water-search/tree/6d8cc58/experiments/reserve-092) were sealed before the first paid call. The current search checked 1,239 whole-frame candidates in 253 requests. The added search checked 435 tile candidates in 146 requests. All 399 requests returned usable answers. Actual token costs through personal Meta Muse Ember 1.0 were $0.051710456 for the control and $0.024166984 for the tile additions, $0.075877440 total under the shared $0.15 ceiling.

[Sealed totals and per-clip results](summary.json) · [Ember answers](verdicts.jsonl) · [Request charges](charges.json) · [Evidence hashes](seal.json)
