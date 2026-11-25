# Blinded pre-call visual audit of the harder pilot

**Result:** 0 visibly on-land person observations among 231 eligible track boxes. The exclusion list is empty (`[]`).

## Coverage

Each observation is one annotated track in one selected second. Track IDs are local to each video. Of the 254 selected seconds, 77 had one box, 77 had two boxes, and 100 had no eligible box.

| Video | Selected seconds | Seconds with boxes | Distinct tracks | Boxes reviewed | On-land exclusions |
|---|---:|---:|---:|---:|---:|
| DJI_0804_0009_40m.mp4 | 26 | 16 | 4 | 29 | 0 |
| DJI_0804_0010_60m.mp4 | 22 | 15 | 4 | 29 | 0 |
| DJI_0804_0012_50m_3.mp4 | 23 | 21 | 7 | 35 | 0 |
| DJI_0804_0017_40m.mp4 | 20 | 9 | 6 | 17 | 0 |
| DJI_0804_0018_40m.mp4 | 41 | 17 | 6 | 33 | 0 |
| DJI_0915_0003_50m.mp4 | 48 | 22 | 4 | 34 | 0 |
| DJI_0915_0018_60m.mp4 | 74 | 54 | 4 | 54 | 0 |
| **Total** | **254** | **154** | **35** | **231** | **0** |

## Review method

The frozen pilot.json had SHA-256 `6b584a523df6c298a38bb8fa147aaeedffcc58d974eb3e8cd51d4239c305fe22`. Each selected JPEG under data/mobdrone-seconds matched its manifest hash. Following the frame and track semantics in probe/cut_mobdrone_clip.py, the review used the manifest’s video_frame to look up the source image and its COCO person boxes. Box coordinates were scaled from the annotation dimensions to the selected JPEG. The observation key uses the manifest’s second and the annotation’s track_id.

I inspected all 254 selected frames in scene views and each of the 231 boxes in a crop showing the surrounding surface. An exclusion required visible land at the boxed person’s position in that second. I reviewed only the approved images and their annotation records. Model flags, model decisions, Ember and final-test scoring played no part in the review.

## Cases requiring interpretation

- In DJI_0804_0012_50m_3.mp4, track 2 at second 23 is aboard a boat. Track 3 at seconds 23, 32 and 33 and track 8 at seconds 36 and 37 are on a board surrounded by water. All six observations remain eligible under the on-land rule.
- In DJI_0804_0018_40m.mp4, breaking surf is visible near tracks 5 and 6 at seconds 67–72. Both boxes remain on the water side of the breaking waves throughout those selected seconds.
- Glare obscures some body detail, for example track 1 at seconds 12–16 in DJI_0804_0009_40m.mp4. Other boxes meet the image edge, for example track 0 at second 37 in DJI_0915_0018_60m.mp4. The visible surroundings show water. No land status was inferred from posture, glare, or an off-frame area.
