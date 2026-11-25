# Trained detector baseline

A published detector trained on SeaDronesSee runs locally, at no cost, on the same validation photos as Ember, and `probe/score.py detector` scores its boxes under the same rule as Ember's sightings.

This folder is licensed under AGPL-3.0 (see [LICENSE](LICENSE)) because the detector code (ultralytics) and the checkpoint are AGPL-3.0. The rest of the repository keeps its own license. The search tool imports nothing from this folder, and `test_run_detector.py` checks that. `open_water_search.py --mode detector-check` runs `run_detector.py` as its own program, with the Python given by `--detector-python`, and reads the `boxes.json` it writes.

## The detector

YOLO26m fine-tuned on SeaDronesSee by dronefreak: [dronefreak/seadronessee-yolo26m](https://huggingface.co/dronefreak/seadronessee-yolo26m) at commit 288991d42f. The weights (`best.pt`, SHA-256 97e29aa8…a8542847) download on first run into `detector/weights/`, which git ignores. Class 0 is swimmer. It trained at 640 pixels.

**The checkpoint was selected on the SeaDronesSee val split.** Its training run validated on that split and kept the best epoch as `best.pt`. Every photo scored here comes from the same split. The model never trained on these photos, but the choice of checkpoint saw them, so expect its numbers here to be slightly optimistic. It also trained on SeaDronesSee's compressed images, and these are the mirror's JPEGs.

## Settings

Fixed on November 24, before any label was viewed:

- **Whole photo:** each photo goes to the model whole, at 640 pixels.
- **Tiles:** each photo goes as the nine tiles of the 3 × 3 grid in `probe/runner.py` `rectangle()`, the same tiles Ember gets close looks at, each at 640 pixels. Boxes move back to whole-photo pixels. Boxes are not merged across tile edges, so a swimmer cut by an edge can give two boxes, and the second scores as a duplicate.
- Both runs keep boxes at confidence 0.25 or more. The scorer then keeps swimmer boxes only, takes the five most confident per photo, and counts a swimmer as found when a box's center lands inside the labeled swimmer box, each labeled box once.
- The better of the two runs is the detector's result. Both are published.

## Results

**The whole-photo run is the detector's result.** It found more swimmers than the tiled run on all three sets, with fewer unmatched sightings.

| Photos | Run | Swimmers | Found | Missed | Unmatched sightings (background, duplicate, wrong class) |
|---|---|---|---|---|---|
| 30 published validation frames | **Whole photo** | 134 | **86** | 48 | 3 (2, 1, 0) |
| 30 published validation frames | Tiles | 134 | 80 | 54 | 12 (8, 3, 1) |
| All 1,547 validation photos | **Whole photo** | 6,206 | **4,283** | 1,923 | 144 (126, 11, 7) |
| All 1,547 validation photos | Tiles | 6,206 | 4,213 | 1,993 | 408 (272, 74, 62) |
| 300 MOBDrone frames | **Whole photo** | 311 | **228** | 83 | 194 (190, 4, 0) |
| 300 MOBDrone frames | Tiles | 311 | 217 | 94 | 400 (383, 17, 0) |

With five sightings per photo, at most 96 of the 30 frames' 134 swimmers and 4,559 of the full split's 6,206 can be found. On the 30 frames, Ember's search found 63–64 swimmers with one close look per frame and 77–78 with all nine, under the same rule (see the main README).

MOBDrone is footage the detector never trained or was selected on. Its label file has one class, person, and every person box is scored as a swimmer, the detector's class 0. The 311 people appear in 192 of the 300 frames, and 309 can be found under the five-sighting limit. MOBDrone labels no boats or gear, so a box on a boat counts as background and no sighting can be wrong class.

## Files

| Path | What it holds |
|---|---|
| `run_detector.py` | Runs the detector on an inputs manifest and writes `boxes.json` and `seal.json` |
| `list_split.py` | Lists the full validation split as an inputs manifest and a scoring manifest, without reading any label |
| `validation-30/` | Runs on the 30 published validation frames (`experiments/zoom-first/validation-30/inputs/manifest.json`) |
| `seadronessee-val/inputs/manifest.json` | Every photo of the split, with size and SHA-256 |
| `seadronessee-val/scoring-only/manifest.json` | Every label file's SHA-256, in the scorer's layout |
| `seadronessee-val/` | Runs on the full split |
| `mobdrone-300/` | Runs on the 300 MOBDrone frames in `mobdrone/frames.json` (`mobdrone/inputs/manifest.json`, scored against `mobdrone/scoring-only`) |
| `*/whole-photo-640/`, `*/tiles-640/` | `boxes.json` (per photo: frame, width, height, and boxes as x1, y1, x2, y2, confidence, class in photo pixels), `seal.json` (SHA-256 of `boxes.json` and of the inputs manifest, with the checkpoint, settings and versions) and `scorecard.json` (printed by `probe/score.py detector`) |

## Run it again

Needs Python 3 with ultralytics 8.4.218 (we used torch 2.15.0 on an Apple Silicon GPU) and network access for the first download of the weights. On a Mac, run outside any sandbox that hides the GPU. Elsewhere pass `--device cpu` or `--device 0`.

~~~
python -m venv detector-venv
detector-venv/bin/pip install ultralytics==8.4.218
export YOLO_CONFIG_DIR=/tmp/ultralytics-config

# The 30 published validation frames: fetch them with probe/fetch_frames.py.
detector-venv/bin/python detector/run_detector.py experiments/zoom-first/validation-30/inputs/manifest.json detector/validation-30/whole-photo-640
detector-venv/bin/python detector/run_detector.py experiments/zoom-first/validation-30/inputs/manifest.json detector/validation-30/tiles-640 --tiles
python3 probe/score.py detector detector/validation-30/whole-photo-640/boxes.json experiments/zoom-first/validation-30/scoring-only
python3 probe/score.py detector detector/validation-30/tiles-640/boxes.json experiments/zoom-first/validation-30/scoring-only

# The full split: download data/images/val/shard_000 and data/labels/val/shard_000 from
# https://huggingface.co/datasets/dronefreak/SeaDronesSee at revision deb1f872, then link them in.
ln -s /path/to/images detector/seadronessee-val/inputs/images
ln -s /path/to/labels detector/seadronessee-val/scoring-only/labels
detector-venv/bin/python detector/run_detector.py detector/seadronessee-val/inputs/manifest.json detector/seadronessee-val/whole-photo-640
detector-venv/bin/python detector/run_detector.py detector/seadronessee-val/inputs/manifest.json detector/seadronessee-val/tiles-640 --tiles
python3 probe/score.py detector detector/seadronessee-val/whole-photo-640/boxes.json detector/seadronessee-val/scoring-only
python3 probe/score.py detector detector/seadronessee-val/tiles-640/boxes.json detector/seadronessee-val/scoring-only

# The 300 MOBDrone frames: fetch the videos with probe/fetch_mobdrone.py, then extract the frames and labels.
python3 probe/extract_mobdrone.py DATA_DIR SAMPLE_DIR
detector-venv/bin/python detector/run_detector.py mobdrone/inputs/manifest.json detector/mobdrone-300/whole-photo-640
detector-venv/bin/python detector/run_detector.py mobdrone/inputs/manifest.json detector/mobdrone-300/tiles-640 --tiles
python3 probe/score.py detector detector/mobdrone-300/whole-photo-640/boxes.json mobdrone/scoring-only
python3 probe/score.py detector detector/mobdrone-300/tiles-640/boxes.json mobdrone/scoring-only
~~~

`run_detector.py` refuses any photo whose SHA-256 or size differs from its manifest, and the scorer refuses any label that differs from its manifest. Running the whole-photo pass on the 30 frames twice on the same machine gave byte-identical `boxes.json`. Another GPU or library version may move boxes slightly, so compare against the seal.

Tests: `python3 -m unittest discover -s detector` (no ultralytics needed).

SeaDronesSee: Varga et al., "SeaDronesSee: A Maritime Benchmark for Detecting Humans in Open Water", WACV 2022. The mirror is CC0-1.0.
