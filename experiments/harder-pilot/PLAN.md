# Seven-clip MOBDrone pilot

Approved November 24, 2026, before any pilot Ember requests. [Decision and thresholds](https://github.com/napiermd/open-water-search/issues/36#issuecomment-7153073358).

## What the test can answer

Can a second look find a labelled swimmer missed throughout the eligible footage by the single-image checks? Can voting across adjacent sightings fill gaps in the record for swimmers already found? Count each labelled identity once within its source clip. A person can appear in several clips under different track IDs. Findings describe these sampled stretches.

## Inputs fixed before model calls

`pilot.json` SHA-256 `6b584a523df6c298a38bb8fa147aaeedffcc58d974eb3e8cd51d4239c305fe22`. The seven clip names are fixed in `prepare.py`. The manifest contains 254 verified frames at one frame per second, 603 detector flags, and 50 contiguous eligible stretches. Forty-six seconds have three eligible neighbors on each side. Reset temporal context at each stretch boundary. All six reserve clips are excluded. The detector is the previously run SeaDronesSee-trained YOLO26m at confidence 0.05, limited to the 12 most confident swimmer flags per second. Freeze the visually audited on-land list before dispatch and set aside annotations without a track ID.

## Arms

1. Detector alone. Use all candidate centers.
2. Current check. Use the existing Muse Ember single-image crop, prompt and structured verdict. Numbered crops for one frame share a request.
3. Padded check. Keep the flag centered at frame edges. Ask separately about a swimmer at the center and a swimmer elsewhere in the crop. Keep either report at the detector's original point. A nearby report receives credit only when that point actually hits the swimmer.
4. Restore-only vote. Start from padded decisions. Use the raw centered yes verdicts as support. Link by nearest previous flag within two seconds and 10% of frame width, one assignment per second, descending detector confidence. For a dismissed flag, require strictly more than half of the linked raw verdicts within three seconds on either side to say centered yes. A nearby-only cue stays available to the reviewer and supplies no evidence of a person at the center for its neighbors. Never use a restored flag as a vote. Retain direct positives immediately. Record the restoration at the earlier of the third later sampled second and the end of the stretch. Report the analogous two-way majority as a secondary check, outside winner selection.
5. Three-image check. Start from padded decisions. For a dismissal with both adjacent seconds in the same stretch, show padded crops at the original flag position at t−1, t and t+1. Ask Ember for one decision about the middle image. Restore a confirmed middle-image flag at t+1. At boundaries retain the single-image decision. Compare this arm separately from the vote.

## Score and decision

Use the same source labels, flag centers and eligibility for every arm. Match a mark within a person's box, breaking overlap by nearest box center. First report unique IDs found, identities gained and lost, and the mean over people of the proportion of their eligible visible seconds marked, including zero for missed people. Report first-alert delay using delivery time, false-mark seconds and linked false episodes per clip and per eligible minute. Also report raw false marks, five-mark-per-frame results and the full-window subset. A restored historical mark fills the record for its observation second. Its receipt time determines when the reviewer learns about it. Simulated video time omits processing and radio delay.

The vote needs a five percentage point improvement in mean coverage over the padded check, retention of every identity found by both single-frame controls (their union), and zero increase in false-mark seconds or false episodes on any clip relative to padded. The three-image check must keep that union, exceed the higher single-image count by at least one, and meet the same false-alarm limits. Verify any claim of a newly found person against the source crops and both controls. Distinguish a genuinely new identity from combining complementary single-image detections. Prefer the three-image arm if both qualify. If neither qualifies, keep the current system. Incomplete arms are ineligible. A partial run cannot establish a seven-clip result.

## Cost and stop

Use the personal Meta Model API, `muse-ember-1.0`, minimal reasoning. Hard ceiling $0.15 including all pilot arms and any unresolved request liability. Reserve worst-case spend before sending. No repeat takes. No more than eight concurrent requests. Stop on the spending ceiling, persistent quota/billing errors, or ten consecutive failures. Seal the answers, costs, and outcome even if no arm qualifies. The six-clip reserve requires a separate decision.
