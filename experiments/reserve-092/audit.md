# Six-reserve visual audit of on-land person labels

**Frozen decision.** All 224 annotated person observations are retained. Zero were visibly on land, and all had track IDs. All 267 selected frames remain in the evaluation, including 69 with no person label.

## Scope and blinding

The selection follows the locked plan at `661b5a8`. The review covered the six reserve clips and 43 selected blocks. Each selected JPEG in `../../data/mobdrone-seconds` matched its manifest SHA-256. Each source video stem and six-digit video-frame number matched exactly one MOBDrone COCO image with matching dimensions. Only category 1 (person) annotations on those images supplied boxes and track IDs.

I inspected all 267 complete frame views in chronological order within each clip and all 224 individual box-context crops. The full views showed shoreline and boat position. The crops showed the surface immediately around each annotation, with corner marks identifying its extent. Only selected seconds appeared in either set of views. A format check displayed candidate fields from an unrelated harder-pilot manifest row. No reserve candidates, scores, marks or verdicts were displayed or used. All review sheets were generated locally outside the repository. No inference or paid calls were made for this audit.

## Decision rule

Exclude an individual observation only when its person is visibly on exposed shore, sand or other land. Use the surface at the person’s location. Retain people in shallow water and cases where glare, the frame edge, a boat or a possible board leaves support uncertain. The land decision applies to the exact video, second and track ID. A missing track ID is counted separately and omitted from tracked scoring.

| Source clip | Selected frames | Frames without a person label | Person boxes reviewed | Distinct track IDs in clip | On land | Missing ID |
|---|---:|---:|---:|---:|---:|---:|
| DJI_0915_0015_50m.mp4 | 146 | 33 | 113 | 8 | 0 | 0 |
| DJI_0915_0017_60m.mp4 | 12 | 7 | 5 | 2 | 0 | 0 |
| DJI_0915_0019_60m.mp4 | 26 | 9 | 17 | 2 | 0 | 0 |
| DJI_0915_0023_50m.mp4 | 35 | 8 | 34 | 4 | 0 | 0 |
| DJI_0915_0027_50m.mp4 | 29 | 11 | 29 | 4 | 0 | 0 |
| DJI_0915_0028_60m.mp4 | 19 | 1 | 26 | 4 | 0 | 0 |
| **Total** | **267** | **69** | **224** | **24** | **0** | **0** |

The 24 IDs count tracks within their source clip. Of the 198 frames with labels, 172 contained one person box and 26 contained two.

## Observations behind the decision

- **Shoreline.** In 0015 at seconds 62–70 and 164–174, pale sand is visible along the right edge of the scene. The labelled figures (tracks 4 and 11 respectively) have green water around their bodies. In 0017 at seconds 10–11, the shoreline is also visible to the right while track 0 lies in water. Shoreline elsewhere in the frame did not trigger an exclusion.
- **Boat.** A white boat is conspicuous in 0015, including seconds 119–125 and 144–149. The corresponding track 6 and track 10 crops show a figure in water clear of the hull. In 0027 at seconds 7–11, the boat and the white-clad track 0 are also separate. No reviewed box clearly placed a person aboard.
- **Board-like shapes and glare.** In 0015, track 3 is small against glare at seconds 19–20. At seconds 28–54 the bright outline changes from curved to elongated against green water. The pixels do not reliably establish whether there is a separate float or board. The observation stays eligible in either case. No reviewed context showed a board resting on exposed land.
- **Frame edges.** Several annotations touch or approach the image boundary, including 0015 track 7 at seconds 135–139 and 0028 track 0 at second 7. The visible surrounding surface is water. The cropped body alone supplied no evidence of land.

## Freeze fingerprints

- `reserve.json` SHA-256 `bb5432ee3a7cab1d8fbf218158fbb9b65971fbe2facebd6084fee99f1bee2fbc`
- `../../data/mobdrone/annotations_person_coco_classes.json` SHA-256 `08b8050efec2972a98af831a17f691c09419674bc06e5876a5d004528cc2b0da`
- `exclusions.json` SHA-256 `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`
