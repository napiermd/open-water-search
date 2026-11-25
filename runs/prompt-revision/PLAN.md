# Revising Ember's check prompt: plan, written before any Ember call

November 24, 2026. Approved by Andrew: tuning under $0.10, confirmation under $0.10.

**Why.** Ember's check dismisses real people. It dismissed 40 on MOBDrone (`runs/verify-mobdrone`), 13 on the live clip (`runs/live-detector-check`) and 110 on AFO (`runs/verify-afo`). Some it called a bird, a seal or a dark shape, some "a person off-centre", and on AFO often "open water between two swimmers". A revised prompt should keep more real people without keeping more false flags.

**What changes.** Only the prompt. Crops, flags (0.05 confidence, at most 12 a frame), structured output, scoring (five marks a photo) and `probe/verify_candidates.py` stay as sealed. Two candidates, in `prompt-a.txt` and `prompt-b.txt`:

- **A** asks whether a person is "at or touching" the centre, and says a person seen from above can be tiny, partly under water, one of a group, or easy to mistake for a bird or seal.
- **B** is A plus what marks a person (a head, arms, legs or a wetsuit) and what does not count (rocks, seaweed, debris, buoys, empty boats or boards, people standing on land).

## Step 1: tuning, on frames already used

**Frames.** The first 300 MOBDrone frames (`mobdrone/frames.json`, flags in `detector/candidates-005/mobdrone-300`) and the 120 seconds of the live clip (`tune/clip`, cut one frame a second as the tool cuts it). The detector's flags on the clip are identical to the sealed live run's.

**The original prompt's numbers, from the sealed runs.** 218 of 311 found with 45 false alarms on the 300 frames (`runs/verify-check/mobdrone-300`), and 101 of 116 with 0 on the clip (`runs/live-detector-check`, rescored under this script's rule): **319 found, 45 false alarms** together.

**Runs.** Each candidate on both sets, one request at a time. Caps: $0.039 on the 300 frames and $0.010 on the clip, per candidate, $0.098 in all. Photos a cap leaves unchecked count as finding nobody.

**Choosing.** Add each candidate's two sets together. A candidate qualifies if it finds more than 319 people with no more than 45 false alarms. The qualifying candidate that finds the most goes to confirmation, then the one with fewer false alarms, then A. **If neither qualifies, the revision stops here.** No confirmation run, the original prompt stays, and the tuning results are published.

The original prompt's numbers come from earlier runs, and Ember answers the same crop differently between runs, so a small gain on this set can be noise. Confirmation exists for that.

## Step 2: confirmation, on AFO photos no step has used

**Photos.** The 214 AFO test-split photos the AFO test did not use (`confirm/frames.json`) all come from 4 of AFO's 17 clips, because that test took every photo of the smaller clips. Checking all 214 costs about $0.081 per prompt, and a fair comparison runs both prompts on the same photos, so it would not fit $0.10. Instead, `confirm/choose_subset.py` takes 108 of them in order of SHA-256 of a fixed seed and the photo name, sized from the flags alone to about $0.042 per prompt (`confirm/subset.json`). No label was read. Only AFO's `human` boxes count as people.

**Runs.** The original prompt and the chosen candidate, each on the same 108 photos with the same flags, up to four requests at a time, each capped at $0.05: $0.10 in all.

**Pass rule.** The candidate passes if it finds more people than the original prompt and makes no more false alarms, counting only photos both runs checked. Both counts and the split of false alarms between empty water and second marks are reported.

**What each result will mean, written now.**

- Pass: the revised prompt becomes the check's default. The README and site show both prompts' results, each labelled with its prompt. The headline stays the sealed MOBDrone and AFO runs, and the video changes only if the headline moves.
- Fail: the original prompt stays, and the candidate's results are published here.
