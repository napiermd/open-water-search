# Detector, then Ember on new MOBDrone frames: plan, written before any Ember call

November 24, 2026. Approved by Andrew with a $0.10 cap.

**Why.** The detector was trained on SeaDronesSee. MOBDrone was filmed with a different camera in a different sea. On the first 300 MOBDrone frames (`runs/verify-check/mobdrone-300`), Ember's check found 218 people with 45 false marks. The detector alone, at the highest confidence that still found as many (0.30), found 222 with 179. That comparison was made after the result, and the same comparison failed on SeaDronesSee photos (`runs/verify-confirm`). It has to be repeated on MOBDrone frames it has not seen.

**Frames.** 300 frames chosen by `select_fresh.py` from video names and frame counts alone (`frames.json`). Every frame is more than 60 frames, about two seconds, from each of the first 300 and from the live clip. They come from 61 of MOBDrone's 66 videos, the same videos as the first 300. Five short videos had no eligible frames.

**Unchanged settings.** Candidates are YOLO26m whole-photo boxes at 0.05 confidence or more, swimmers only, at most 12 per photo (`detector/candidates-005/mobdrone-fresh-300`). They were counted before any label was read: 694 candidates in 207 frames. Ember's check is `probe/verify_candidates.py` exactly as in `runs/verify-check` and `runs/verify-confirm`. One scoring rule, five sightings per photo.

**The detector's trade-off.** Using the same 0.05 boxes, score the detector alone at every confidence from 0.05 to 0.95 in steps of 0.01, keeping its five most confident boxes per photo.

**Pass rule, the same as the confirmation's.** Let F and U be the people found and false marks of detector-then-Ember. Take the highest confidence at which the detector alone still finds at least F people, and its false marks D there. Detector-then-Ember passes if U is less than D. The headline reduction is 1 − U / D, reported as measured. If the cap stops the run early, frames not checked count as finding nobody.

**What a pass would support.** On footage from a camera and sea the detector was not trained on, Ember's check removes false alarms that the detector's own threshold cannot remove without losing people. The frames come from the same videos as the first 300, so a pass shows the result repeats on new moments of that footage. It does not show the result holds on other footage.

**Budget.** $0.10. The run stops before a request could cross it.
