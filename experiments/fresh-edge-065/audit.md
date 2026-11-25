# Blinded land audit for fresh-edge-065

**Zero land exclusions.** All 64 annotated person-seconds across nine clip-local tracks remain eligible. The review covered all 86 selected frames, including 25 without a person annotation.

I used the plan locked at `a672f12` and verified the supplied SHA-256 of `fresh.json`. Every selected JPEG in `data/mobdrone-seconds` matched its manifest hash. Each video stem and six-digit source frame number matched exactly one MOBDrone COCO image, with matching dimensions. I inspected every full-frame view and a separate context crop for every category 1 box, using the source annotation to mark the person. All boxes had track IDs. Detector flags and model verdicts stayed blinded. The audit used no model calls.

The exclusion rule applies to an individual video, second and track ID only when the person is visibly on exposed land. All second ranges below are inclusive. Track IDs are local to each video.

| Video | Seconds | Frames | Frames without a person label | Person-seconds | Track IDs | Visual basis for retention |
|---|---|---:|---:|---:|---|---|
| DJI_0915_0004_50m.mp4 | 27–36 | 10 | 0 | 10 | 1 | Ripples and splashes surround the figure throughout the sequence. |
| DJI_0915_0005_60m.mp4 | 23–34 | 12 | 1 | 14 | 0, 1 | Both figures are in green water, including the three seconds when both are labeled (32–34). |
| DJI_0915_0008_50m.mp4 | 0–3 | 4 | 0 | 4 | 1 | The figure near the right frame edge is surrounded by water in all four crops. |
| DJI_0915_0011_30m.mp4 | 15–26 | 12 | 0 | 12 | 0 | The figure enters at the top edge over water. Water remains visible around the body as it comes fully into view. |
| DJI_0915_0013_40m.mp4 | 56–67 | 12 | 8 | 4 | 3 | Beach is visible on the right. At seconds 64–67 the labeled figure is offshore in green water. |
| DJI_0915_0014_40m.mp4 | 54–65 | 12 | 9 | 3 | 3 | At seconds 54–56 the figure is clipped by the left edge beside a ring of disturbed water. The shoreline is across the frame. |
| DJI_0915_0022_40m.mp4 | 53–64 | 12 | 4 | 8 | 1 | The figure floats in gray-green water through second 60, when it reaches the bottom edge. |
| DJI_0915_0031_20m.mp4 | 42–53 | 12 | 3 | 9 | 3 | Ripples trail the figure through the water as it approaches the lower edge at second 50. |
| **Total** | | **86** | **25** | **64** | **9 clip-local tracks** | |

## SHA-256 fingerprints

| File | SHA-256 |
|---|---|
| `fresh.json` | `8265eabefbaa04b1ab723ec50f09283651768c6ba1b7a44b7d46c03e8a992d7d` |
| `data/mobdrone/annotations_person_coco_classes.json` | `08b8050efec2972a98af831a17f691c09419674bc06e5876a5d004528cc2b0da` |
| `exclusions.json` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
