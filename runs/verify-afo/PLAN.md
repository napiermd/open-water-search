# Detector, then Ember on AFO: plan, written before any Ember call

November 24, 2026. Approved by Andrew with a $0.10 cap.

**Why.** On 300 new MOBDrone frames (`runs/verify-mobdrone`), Ember's check kept the same 210 people as the detector alone with 38 false alarms against 166. On SeaDronesSee, the detector's own footage, the same check lost (`runs/verify-confirm`). This test asks whether the MOBDrone result holds on a second dataset the detector never saw, from a different place and different drones.

**Photos.** AFO, the Aerial dataset of Floating Objects (Gąsienica-Józkowy, Knapik and Cyganek, 2021), CC BY-NC-SA 3.0, used non-commercially. 300 of the 514 photos in its test split, chosen by `select_afo.py` from file names alone, spread across all 17 of the split's source clips (`frames.json`). Every photo in that split has at least one labelled object. The trained detector never saw AFO.

**What counts as a person.** Only AFO's `human` boxes. Boxes of its other classes (wind or SUP board, boat, buoy, sailboat, kayak) are left out of the scoring labels, so a kept mark on one of them is a false alarm.

**Unchanged settings.** Flags are YOLO26m whole-photo boxes at 0.05 confidence or more, swimmers only, at most 12 per photo (`detector/candidates-005/afo-300`). They were counted before any label was read: 1,951 flags in 255 of the 300 photos. Ember's check is `probe/flag_check.py` through `probe/verify_candidates.py`, exactly as in `runs/verify-mobdrone`. One scoring rule, five marks per photo.

**The detector's trade-off.** Using the same 0.05 boxes, score the detector alone at every confidence from 0.05 to 0.95 in steps of 0.01, keeping its five most confident boxes per photo.

**Pass rule, the same as MOBDrone's.** Let F and U be the people found and false alarms of detector-then-Ember. Take the highest confidence at which the detector alone still finds at least F people, and its false alarms D there. Detector-then-Ember passes if U is less than D. The headline reduction is 1 − U / D, reported as measured. If the cap stops the run early, photos not checked count as finding nobody.

**Reported beside the result.** The most people anyone could find under the five-mark limit, the split of false alarms between empty water and second marks, and the detector alone at its published 0.25.

**What each result will mean, written now.**

- Pass: the claim held on two datasets the detector never saw, MOBDrone and AFO, from different places and drones. The headline names both.
- Fail: Ember's check helped on MOBDrone and not on AFO. The headline narrows to MOBDrone, the video's line about where the check helps is re-recorded, and both runs stay published.

**Budget.** $0.10. The run stops before a request could cross it. Expected cost, from the per-request and per-crop prices of the sealed runs, is about $0.07.
