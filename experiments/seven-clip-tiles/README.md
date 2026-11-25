# Tiled detection recovered one of three missed track IDs

The same local SeaDronesSee-trained YOLO26m saw nine nonoverlapping tiles from each of the 254 saved MOBDrone pilot frames. Its swimmer confidence cutoff was 0.05. Both runs kept up to 12 swimmer flags per original frame. Model API spend was $0.

| Detector input | Labelled tracks found | Correct person-seconds | Candidate flags | False-alarm episodes |
|---|---:|---:|---:|---:|
| Whole frame | 32/35 | 186/231 | 603 | 173 |
| Nine tiles | 33/35 | 177/231 | 1,349 | 566 |

The tiled detector retained all 32 previously found track IDs. In `DJI_0804_0012_50m_3` it also flagged paddleboard track 8 at second 37, one of its two eligible seconds. Its fourth-ranked swimmer box scored 0.1077. Its center (249.985, 935.295) fell inside the labelled box (239.42, 934.23) to (263.94, 952.66), about one pixel inside its top edge. The wider detection box includes the board. The image supports a cue for a reviewer to inspect the paddler.

Track 2 on the boat and track 3 on the board still had zero swimmer-center hits, including before the 12-flag limit. Track IDs 3 and 8 may represent the same paddler appearing under two IDs. The score counts the recovered ID once. This was a retrospective check on seven known clips and includes no evidence about how Ember would judge the additional crops. The six reserve clips and current Ember check were outside the experiment.

## Reproduce from the saved inputs

From the repository root, use the pilot photos and cached checkpoint referenced in the [plan](PLAN.md). The runner checks every image hash and the pinned weight hash. The scorer checks the saved whole-frame result and the seals before comparing track identities.

```sh
p=experiments/seven-clip-tiles
YOLO_OFFLINE=true detector-venv/bin/python detector/run_detector.py "$p/inputs.json" "$p" --tiles --device mps --min-confidence 0.05
python3 "$p/compare.py"
```

[Results per clip and missed track](comparison.json) · [Model and input hashes](seal.json)
