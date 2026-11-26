# Seven harder MOBDrone clips

**Every method found the same 32 of 35 labelled identities.** The current single-image Ember check reduced 173 detector false-alarm episodes to 26. The vote filled in some missed seconds for people already found. Both temporal methods increased false alarms over the padded single-image check and neither met its preregistered threshold. Keep the current check.

| Method | Person IDs found | Correct person-seconds (of 231) | Mean coverage per person | Seconds with a false mark | False-alarm episodes |
|---|---:|---:|---:|---:|---:|
| Detector alone | 32 | 186 | 77.69% | 126 | 173 |
| Current single-image Ember check | 32 | 160 | 65.75% | 35 | 26 |
| Padded single-image check | 32 | 168 | 70.16% | 50 | 64 |
| Padded check plus restore-only vote | 32 | 179 | 74.64% | 57 | 66 |
| Padded check plus three-image second look, delivered marks | 32 | 176 | 72.88% | 57 | 66 |

Each labelled identity contributes equally to mean coverage, including the three with zero marks. Each person in each observed second contributes once to the person-second count. False marks are grouped into episodes separately within each eligible stretch. The 254 sampled seconds came from 50 stretches of previously sampled recordings. The six clips set aside for confirmation were outside this pilot.

## Who was missed?

All three missed IDs came from `DJI_0804_0012_50m_3` and no candidate center landed on them. Looking back at the six observations, ID 2 was aboard a boat at second 23. IDs 3 and 8 were on a paddleboard at seconds 23, 32–33 and 36–37. These are dataset track IDs. The footage does not establish whether the paddler under the two IDs was a different individual. They remain in the denominator under the [pre-call audit](audit.md). No single-image control missed a labelled identity that a temporal method found.

## What the extra context bought

The vote restored 11 correct person-seconds over the padded control. Mean coverage rose 4.48 percentage points, short of the required five, and false-mark seconds increased on three clips. These are retrospective repairs to the search record. A restored mark reaches the reviewer up to three sampled seconds after its observation.

The second look added eight correct person-seconds. Of 166 follow-up calls, 160 returned usable verdicts. The six unusable replies delivered no marks and disqualify this arm under the plan. Checking all six flag centers against the labels showed that accepting every one would add six false marks and zero people. Neither result earns a claim about finding someone earlier or reducing human review time.

## Cost and replay

The [plan](PLAN.md) and [input manifest](pilot.json) were published before paid requests. Meta Muse Ember 1.0 received 179 current-check calls, 179 padded-check calls and 166 follow-ups through the personal Meta Model API. Tokens cost $0.030040632, $0.032979476 and $0.027371832 respectively. The total was **$0.090391940** under the $0.15 ceiling, including the six unusable replies. The vote reused recorded answers at zero extra cost.

[Verdicts](verdicts.jsonl) · [Request charges](charges.json) · [Full and per-clip results](summary.json) · [SHA-256 seal](seal.json)

From the repository root, replay the marks offline and reproduce the per-person scores using the MOBDrone COCO annotations. The charge log identifies follow-ups that produced no usable verdict.

```sh
p=experiments/harder-pilot
python3 "$p/build_marks.py" "$p/verdicts.jsonl" /tmp/ows-seven-marks.json --charges "$p/charges.json"
python3 "$p/score_pilot.py" --marks /tmp/ows-seven-marks.json --exclusions "$p/exclusions.json" \
  --annotations /path/to/annotations_person_coco_classes.json > /tmp/ows-seven-score.json
```

The replay reports delivered marks. `summary.json` also records each method’s eligibility for selection and the check on the missing verdicts. MOBDrone imagery and the annotation download are external to this repository.
