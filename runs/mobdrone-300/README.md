# MOBDrone: Ember on 300 frames the trained detector never saw

Ticket #15. The 300 MOBDrone frames listed in `mobdrone/frames.json` (committed before any frame or label was viewed) ran through the default fixed method: one overview and two close looks per frame, grounding format, on November 24, 2026. MOBDrone labels only people, so every person counts as a swimmer, and a mark on a boat or buoy counts as a mark with no person.

| 311 labeled people in 300 frames | Found | Missed | Marks with no person | Cost |
|---|---|---|---|---|
| Trained detector, whole photo at 640 (`detector/mobdrone-300`) | 228 | 83 | 194 | $0 (local) |
| Trained detector, 3×3 tiles at 640 | 217 | 94 | 400 | $0 (local) |
| Ember, fixed method (this run) | 205 | 106 | 232 | $0.1364 |

The trained detector is more accurate here as well. Ember was never trained on drone photos and found 205 of the 311 people (66%) on footage new to both.

The 300 frames are spread across 66 videos and are not consecutive, so the possible people in this search record merge sightings from unrelated frames and say nothing about the merge rule. That check uses the live clip in `runs/live-clip`.

`seal.json` holds the SHA-256 of the search record and calls log as written. The published copies have Meta's response and message IDs removed. MOBDrone is by Cafarelli et al. (arXiv 2203.07973), CC BY 4.0.
