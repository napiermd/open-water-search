# Open Water Search

A drone over open water takes thousands of wide photos an hour. The people in them are tiny: in the image size Muse Ember reads, a typical swimmer is about 11 pixels across. Open Water Search has Ember take one cheap look at each whole frame, decide which patch of water deserves a close look, and mark anyone it finds. A reviewer gets a short queue of marked crops plus a map of the water nobody has checked yet.

Built during the Muse Ember Hackathon, November 23 to December 2, 2026.

## Run it

```
pip install pillow
export MODEL_API_KEY=your-meta-model-api-key
python probe/open_water_search.py path/to/frames --out results --budget 0.05
open results/report.html
```

Point it at a folder of .jpg, .jpeg or .png frames. Each frame gets one overview, in which Ember ranks the nine tiles of a 3 x 3 grid, and then close looks at its top two tiles. Change the number with `--looks`, and pass the key with `--key-file` instead of the environment variable if you prefer. Before each request, the tool checks that the request's worst-case cost fits within `--budget`. If the budget runs out, the tool stops and says so in the report.

The results folder holds:

- `report.html`: the reviewer queue, highest confidence first, and a coverage map of every frame showing which tiles had a sighting, which Ember checked without reporting anyone, and which never got a close look
- `queue.json`: up to five sightings per frame, in source-image pixels
- `coverage.json`: every tile's status for every frame
- `calls.jsonl`: every Ember request, with its token usage, cost and answer

An overview plus two close looks cost about $0.00052 per frame in our runs, or $1.88 per 3,600 frames. Requests go one at a time, about 4.4 seconds per frame.

## What we measured

We compared three ways to spend close looks on the same frames, using the same recorded Ember answer for every crop. Only the order in which tiles are opened differs. Each cell counts labeled swimmers found under a limit of five sightings per frame. Ranges cover the two answer sets, one from each search's pass over the frames.

**Validation: 30 untouched SeaDronesSee validation frames, 134 swimmers.** The measure and the pass rule were written down before any call.

| Close looks per frame | 1 | 2 | 3 | All 9 |
|---|---|---|---|---|
| Ember picks the tile from one overview | 63–64 | 74 | 75–77 | 77–78 |
| Always zoom the center first | 30–31 | 31–33 | 34–37 | 76–78 |
| Fixed grid order | 7 | 16 | 24–25 | 77–78 |

**First run: 30 SeaDronesSee training frames, 158 swimmers.** This comparison was defined after the labels were opened, which is why we repeated it.

| Close looks per frame | 1 | 2 | 3 | All 9 |
|---|---|---|---|---|
| Ember picks the tile from one overview | 65–73 | 83–92 | 86–95 | 85–94 |
| Always zoom the center first | 28–38 | 30–41 | 42–53 | 85–94 |
| Fixed grid order | 7–10 | 18–24 | 36–44 | 85–94 |

From one overview, Ember's first-ranked tile held a labeled swimmer in 26 of 30 first-run frames and 24 of 30 validation frames.

We also planned a head-to-head at equal spend, in which each search used its own answers. It does not support a claim either way. In the first run, both searches eventually sent identical crops, and Ember returned a different number of marks on 12 of those 270 crops between passes. That variation is as large as the gap between the searches. In validation, the totals were 78 against 77 with our reader and 75 against 65 with a stricter one. Both scorecards are published.

## Reproduce the numbers

```
pip install pillow
python probe/fetch_frames.py      # downloads the 60 frames and labels from the pinned mirror and checks every hash
python probe/check.py             # offline checks with simulated answers, no API calls
python probe/score.py             # rebuilds the first-run scorecards and compares them with live/
python probe/score.py validation  # the same for validation/live/
```

The order tables are under `order_table` in each `score.json`. `score.py` refuses to score unless the trace matches its seal.

To make your own sealed run on macOS, move `live/` or `validation/live/` aside. Then, with `MODEL_API_KEY` set, run `sh probe/isolate.sh runner.py --dataset probe --prior-nanodollars 0` from the repository root. The launcher uses `sandbox-exec` so the inference process cannot read the label folders. The runner caps a run at $0.49, reserves each request's worst-case cost before sending it, and stops after ten unreadable answers in a row.

## Run record

- **Settings.** Model `muse-ember-1.0` on the Meta Model API, minimal reasoning, a 2,000-token output limit, 3 x 3 tiles resized to at most 1,000 pixels on the long edge, and JPEG quality 90. The prompts are in `probe/runner.py`, and their hashes are in each `settings.json`.
- **False start.** The first attempt used a 384-token output limit. Ember spent it on reasoning and returned empty answers for 14 of 16 overviews, which tripped the failure breaker after 46 calls ($0.0075). Earlier in that attempt, the reader was amended to accept a bare `[]` as an empty answer. The attempt is preserved, with response IDs removed, in `false-start/`. It was restarted from scratch with the 2,000-token limit, and its cost counted toward the $0.49 cap.
- **0–1,000 coordinates.** Some close looks returned points on Meta's 0–1,000 image grid instead of the fractions the prompt asked for. Before any label was opened, we fixed a rule that converts them. `score.json` applies it, and `score-strict.json` discards those answers.
- **Frames.** The first run's 30 frames were drawn by a seeded hash from a 400-image local training pool, listed in `inputs/training-pool.txt`. Validation drew 30 frames from the 1,547-image validation split, skipping any within 8 bits of a pool image on a 64-bit difference hash (`probe/select_validation.py`). Fifteen of the first 45 candidates were skipped, which suggests the splits share source videos. Nothing was tuned on any frame.
- **Spend.** $0.0662 for the first run plus $0.0075 for the false start, $0.0670 for validation, and $0.0023 for the four-frame tool test in `examples/tool-test/`.

## What is and isn't here

The traces are Ember's replies as returned, minus Meta's response and message IDs. `redaction.json` gives the SHA-256 of each original trace, which matches its `seal.json`, and of the redacted copy. No API key is stored anywhere in the repository. The SeaDronesSee images and labels are not included. `fetch_frames.py` downloads them from the mirror at revision `deb1f872` and checks each one against the SHA-256 recorded in the manifests.

## Credits and license

Frames and labels come from SeaDronesSee (Varga, Kiefer, Messmer and Zell, University of Tübingen; [arXiv:2105.01922](https://arxiv.org/abs/2105.01922)), released under CC0 and read here through the [dronefreak/SeaDronesSee](https://huggingface.co/datasets/dronefreak/SeaDronesSee) mirror. The code is MIT licensed.
