# Detector, then Ember: confirmation plan, written before any Ember call

November 24, 2026. Approved by Andrew with a $0.30 cap.

**Why.** On 330 photos (`runs/verify-check`), detector-then-Ember found 296 people with 51 false marks. The detector alone, set to find as many, made 171. That comparison was chosen after the result, so it has to be repeated on photos it has not seen.

**Photos.** The 1,517 SeaDronesSee validation photos left after removing the 30 earlier validation photos (`inputs/manifest.json`, `scoring-only/manifest.json`). Neither set of settings was tuned on them.

**Unchanged settings.** Candidates are YOLO26m whole-photo boxes at 0.05 confidence or more, swimmers only, at most 12 per photo (`detector/candidates-005/validation-1517`, counted before any label was read: 6,515 candidates in 1,251 photos). Ember's check is `probe/verify_candidates.py` exactly as in `runs/verify-check`. One scoring rule, five sightings per photo.

**The detector's trade-off.** Using the same 0.05 boxes, score the detector alone at every confidence from 0.05 to 0.95 in steps of 0.01, keeping its five most confident boxes per photo.

**Pass rule.** Let F and U be the people found and false marks of detector-then-Ember. Take the highest confidence at which the detector alone still finds at least F people, and its false marks D there. Detector-then-Ember passes if U is less than D. The headline reduction is 1 − U / D, reported as measured. If the cap stops the run early, photos not checked count as finding nobody.

**Budget.** $0.30. The run stops before a request could cross it.
