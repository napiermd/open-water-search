# Scale run: all 1,547 SeaDronesSee validation photos

Ticket #12. Every photo in the SeaDronesSee validation split (mirror dronefreak/SeaDronesSee at revision deb1f872, listed in `detector/seadronessee-val/inputs/manifest.json`) ran as one flight through the default fixed method on November 24, 2026: one overview and two close looks per photo, grounding format, up to 8 requests at once, spending cap $1.47.

| 6,206 swimmers in 1,547 photos | Found | Missed | Marks with no swimmer | Cost | Time |
|---|---|---|---|---|---|
| Ember, fixed method (this run) | 3,876 (62%) | 2,330 | 874 | $0.9571 | 44 min |
| Trained detector, whole photo at 640 | 4,283 (69%) | 1,923 | 144 | $0 (local) | about 2 min |
| Trained detector, 3×3 tiles at 640 | 4,213 (68%) | 1,993 | 408 | $0 (local) | about 12 min |

The trained detector is more accurate and far cheaper on this dataset, and its checkpoint was chosen on this same split, so its numbers lean optimistic.

- **Cost:** $0.9571 for 4,641 calls, or about $0.00062 per photo. At one photo a second that is about $2.23 per hour of footage.
- **Speed:** 35.1 photos a minute over the whole run (2,646 s), short of the 60 a minute needed to keep pace with one photo a second.
- **Reliability:** every overview was read, with no lost requests and no unreadable answers. The first attempt ended after 57 calls when one request timed out; the fix (one retry, then only that request is lost) is in commit e68172f, and that attempt's $0.0208 is counted in the project's spending.
- **The earlier 30 validation photos** are part of this split. Within this run they scored 76 of 134 found, 58 missed and 19 marks with no swimmer (`scorecard-earlier-30.json`), for $0.0185 across their 90 calls. Their requests ran interleaved with the rest of the flight, so photos per minute is measured for the whole run only. The format check found 79 on the same photos in a separate pass.

The photos are not one continuous flight, so possible people here merge sightings from unrelated photos. The merge rule is checked on the live clip in `runs/live-clip`.

`scoring-only/manifest.json` lists the same labels and hashes as the detector's, in this run's order. `seal.json` holds the SHA-256 of the search record and calls log as written. The published copies have Meta's response and message IDs removed.
