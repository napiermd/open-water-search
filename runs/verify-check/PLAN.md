# Detector, then Ember: plan, written before any Ember call

November 24, 2026. Approved by Andrew with a $0.30 cap across both sets.

**Question.** Does Ember checking a trained detector's candidates beat the detector alone?

**Candidates.** YOLO26m (`detector/`), whole photo at 640 pixels, swimmer boxes (class 0) at 0.05 confidence or more, at most the 12 most confident per photo. Boxes are in `detector/candidates-005/`. Counts were taken before any label was read: 742 candidates in 213 of the 300 MOBDrone frames, and 137 in 25 of the 30 validation photos.

**Ember's check.** `probe/verify_candidates.py`, one request per photo with any candidate, on muse-ember-1.0 with minimal reasoning. Each candidate is a square crop centred on its box, three times the box's longer side and at least 96 pixels, sent at 224 × 224 and numbered. Structured output forces an answer for every crop: person in the water at the centre (true or false), confidence, and a few words on what is there.

**Sightings and scoring.** Every accepted candidate becomes a sighting at its box's centre, ranked by Ember's confidence and then the detector's. The project's one scoring rule keeps the five best per photo, counts a sighting inside a labeled box as a find, and finds each box only once.

**What it has to beat.** The detector alone, as published: whole photo at 640, 0.25 confidence, top five per photo.

| Set | Found | Marks with no swimmer |
|---|---|---|
| MOBDrone, 300 frames (311 people) | 228 | 194 |
| Validation, 30 photos (134 swimmers) | 86 | 3 |
| **Both** | **314** | **197** |

**Pass rule, on both sets added together.** Detector-then-Ember beats the detector alone if it finds at least 314 with fewer than 197 marks with no swimmer, or finds more than 314 with no more than 197. Anything else is reported as not beating it.

**Budget.** $0.25 for the MOBDrone frames and $0.05 for the validation photos. Each run stops before a request could cross its cap. If it passes, the full validation split follows under a cap of at most $1.00.
