# The November 23 zoom-first experiment

The project's first day. Ember searched each frame alone: one overview ranked the nine tiles of a 3 × 3 grid, and close looks went to the top-ranked tiles. The two sealed runs here are the ones behind the one-zoom order table in [docs/results.md](../../docs/results.md).

| Folder | What it holds |
|---|---|
| `training-30/` | The first run, on 30 SeaDronesSee training frames: the inputs manifest, the sealed trace and scorecards in `live/`, and the scoring manifest |
| `validation-30/` | The repeat on 30 untouched SeaDronesSee validation frames, laid out the same way |
| `false-start/` | The first attempt, stopped by its failure breaker after 46 calls when a 384-token output limit left answers empty |
| `tool-test/` | The four-frame paid test of the search command, replayed by the offline tests |

## Moved on November 24

These folders lived at the top of the repository until November 24. Sealed files still name the paths they had when they were written, and they were moved byte for byte so their seals still verify. The code reads them from here.

| Path named inside sealed files | Path now |
|---|---|
| `inputs/` | `experiments/zoom-first/training-30/inputs/` |
| `live/` | `experiments/zoom-first/training-30/live/` |
| `scoring-only/` | `experiments/zoom-first/training-30/scoring-only/` |
| `validation/` | `experiments/zoom-first/validation-30/` |
| `false-start/` | `experiments/zoom-first/false-start/` |
| `examples/tool-test/` | `experiments/zoom-first/tool-test/` |

`python probe/score.py` and `python probe/score.py validation` rebuild both runs' scorecards from their sealed traces and check them against the published ones. The images and labels download with `python probe/fetch_frames.py`.
