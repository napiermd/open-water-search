# Centering the pin recovered the swimmer at second 136

Across all six previously scored clips, replacing just the 120 edge decisions found 24 of 24 labelled tracks. The current search found 23. The recovered track was visible at the top of the frame in DJI_0915_0015_50m. Ember accepted the person at seconds 136, 137 and 138. At second 136 its saved original reply was “partial swimmer at top edge, centre empty water.” Its padded reply was “person in white in water,” with a yes at 0.95 confidence.

| Across the same 267 frames | Current | Centered edge crops |
|---|---:|---:|
| Labelled tracks found | 23/24 | 24/24 |
| Correct person-seconds | 183/224 | 197/224 |
| False marks | 83 | 100 |
| Seconds with false marks | 48 | 60 |
| Linked false-alarm episodes | 52 | 60 |

The paired replacements added 19 false marks and removed two. They added 15 correct marks and removed none. Repeated marks on the same person in the same second count once for person-seconds. False episodes use the original temporal linking rule. Each edge decision was rerun on the original frame pixels with black padding outside the picture. Only edge flags were batched, and Ember can vary between calls. The known miss motivated this test, so the result describes these clips and does not establish the effect on new footage.

Personal Meta Muse Ember 1.0 returned all 120 answers across 85 requests. The token charge was $0.009897152 under the $0.05 ceiling. The production search was not changed.

[Locked plan](PLAN.md) · [Paired results and changed marks](summary.json) · [Saved answers](verdicts.jsonl) · [Request charges](charges.json) · [Evidence hashes](seal.json)

## Offline replay of an edge-only cutoff

At **Ember confidence ≥0.65** on padded edge yeses, the reviewer still received the swimmer at seconds **136, 137 and 138**. Across the six clips this gave 24/24 labelled tracks, 189 correct person-seconds and 48 linked false-alarm episodes. The original check had 23/24, 183 and 52. Relative to the original decisions the replay introduced two false marks and suppressed eight, for 77 false marks overall. This is a net change in linked episodes; filtering can split or join an episode.

| Rule | Tracks | Correct person-seconds | False-alarm episodes |
|---|---:|---:|---:|
| Original crops | 23/24 | 183 | 52 |
| Padded, any yes | 24/24 | 197 | 60 |
| Padded, ≥0.60 | 24/24 | 190 | 51 |
| Padded, ≥0.65 | 24/24 | 189 | 48 |
| Padded, ≥0.70 | 24/24 | 183 | 47 |

Moving from 0.65 to 0.70 saved one more episode while losing six correctly marked person-seconds. The proposed 0.65 threshold was selected retrospectively on these same clips. Replay used the saved verdicts and the linked-episode scorer, with zero API calls. [Full sweep](cutoff-sweep.json) · [Replay code](replay_cutoffs.py).
