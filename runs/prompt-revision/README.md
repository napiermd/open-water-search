# Revising Ember's check prompt: results

The plan in `PLAN.md` was committed (6b3317a) before any Ember call. Tuning ran on November 24, 2026, with muse-ember-1.0, and cost $0.0905 for 624 requests under a $0.098 cap. Every run finished without stopping early.

**Neither candidate qualified, so the revision stopped at tuning.** Under the plan there was no confirmation run, and the original prompt stays. The 214 untouched AFO photos remain unused.

| Tuning set: first 300 MOBDrone frames and the live clip | Found | False alarms |
|---|---|---|
| Original prompt (sealed runs) | 319 (218 + 101) | 45 (45 + 0) |
| Candidate A: "at or touching" the centre, and people can look like birds or seals | 306 (209 + 97) | 81 (81 + 0) |
| Candidate B: A, plus what marks a person and what doesn't count | 307 (206 + 101) | 26 (26 + 0) |

To qualify, a candidate had to find more than 319 with no more than 45 false alarms.

**What went wrong.** Both candidates were meant to stop Ember dismissing real people, and both dismissed more of them. On the 300 MOBDrone frames, counting flags whose centre lies on a labelled person:

| | Kept a person | Dismissed a person | Kept a non-person | Dismissed a non-person |
|---|---|---|---|---|
| Original prompt | 227 | 38 | 40 | 437 |
| Candidate A | 217 | 48 | 78 | 399 |
| Candidate B | 216 | 49 | 16 | 461 |

Widening the centre to "at or touching" (A) mostly let in more things that aren't people. Telling Ember what a person looks like and what doesn't count (B) made it stricter: it kept 16 non-people instead of 40, but it also turned away more real people. Some of those are labelled people standing on sand, which MOBDrone counts as people and B's wording rules out. B cutting false alarms from 45 to 26 is a real effect on this set, but the plan asked for more people found, and B found fewer.

The original prompt's numbers come from earlier runs, and Ember answers the same crop differently between runs, so differences of a few people are within that variation. A difference of 38 against 49 dismissed people, in the opposite direction from the aim, is not.

`tune/tuning.json` has every run's numbers and cost. Each run folder has its scorecard, sightings, summary and `seal.json` with the SHA-256 of `checks.jsonl` as written. The published `checks-redacted.jsonl` copies have Meta's response and message IDs removed.
