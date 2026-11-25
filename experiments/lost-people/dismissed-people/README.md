# Why Ember's check dismisses real people

A free analysis of the sealed runs, made on November 24, 2026 for the map [Get the lost people back](https://github.com/napiermd/open-water-search/issues/29). It made no Ember call. `sort_dismissed.py` rebuilds every number here.

Across five sealed runs the detector put 1,862 flags on labelled people. Ember's check kept 1,652 and dismissed 210, about one in nine. Each dismissal comes with a few words from Ember saying what it saw. Sorting those words by keyword gives seven reasons.

| What Ember said was there | MOBDrone, first 300 frames | MOBDrone, second 300 frames | AFO, 300 photos | Live clip, re-run | Live clip, first take | All |
|---|---|---|---|---|---|---|
| A person, but away from the centre of the crop | 12 | 3 | 59 | 4 | 3 | **81** |
| An animal | 11 | 17 | 8 | 8 | 6 | **50** |
| A board, boat or float | 2 | 3 | 18 | 0 | 0 | **23** |
| Foam, a splash or a wake | 1 | 7 | 12 | 0 | 0 | **20** |
| An unclear object | 3 | 4 | 11 | 1 | 0 | **19** |
| A person on land | 9 | 6 | 0 | 0 | 0 | **15** |
| Empty water | 0 | 0 | 2 | 0 | 0 | **2** |
| **Real people dismissed** | 38 | 40 | 110 | 13 | 9 | **210** |
| Flags on real people | 265 | 268 | 1,101 | 114 | 114 | 1,862 |

## What the reasons show

**81 of the 210 were people Ember saw and said so.** The check asks whether a person in the water is at the centre of the crop. In these 81 Ember answered that a person was there but off to one side, or that the centre was water between two swimmers. In 77 of the 81 the crop gave it cause. Either the flag sat so near the photo's edge that the crop could not be centred on it (34), or the crop held several labelled people (56), or both. AFO's crowded groups account for 59.

Crops that are off centre get dismissed almost four times as often. Of the 150 flags on people whose crop was pushed in by the photo's edge, Ember dismissed 52 (35%). Of the other 1,712, it dismissed 158 (9%).

**89 were a centred person Ember took for something else.** It called 50 an animal (a bird, seal, dolphin or turtle), 20 foam or a splash, and 19 an unclear object. The person was a median of 3% to 8% of the crop's width from its centre and 78 to 105 pixels long in the 224-pixel crop. Size and position do not explain these. The animal crops often show a clear head and arms from above. The foam and unclear crops are mostly people under the surface or in broken water, where one still image is ambiguous.

**23 were on a board, boat or float.** Some are a person lying on a paddleboard. Some are an empty board that the labelled person stands beside.

**15 were people on a beach.** MOBDrone labels everyone, including people standing on sand. Ember was asked for a person in the water and dismissed them. Under the project's claim these dismissals are correct, and the score counts them as lost people.

## What each reason points to

| Reason | Count | What could get them back |
|---|---|---|
| Seen but off centre | 81 | Keep a flag when Ember reports a person in the crop, or centre the crop by padding at the photo's edge. Needs no vote. |
| Taken for an animal, foam or an unclear object | 89 | Other seconds of the same flag: a vote, or several seconds shown to Ember at once. |
| On a board, boat or float | 23 | Mixed. A scoring question as much as a system one. |
| On land | 15 | Nothing. Set these labels aside when scoring. |

These are leads for the map's open questions and have not been tested.

## Measurements

| What Ember said was there | Dismissed | Person's distance from the crop's centre (median) | More than a quarter of the crop from centre | Crop pushed in by the photo's edge | Several people in the crop | Person's length in the crop (median, of 224 pixels) |
|---|---|---|---|---|---|---|
| A person, but away from the centre of the crop | 81 | 12% | 30 | 34 | 56 | 82 |
| An animal | 50 | 3% | 3 | 5 | 0 | 78 |
| A board, boat or float | 23 | 4% | 5 | 6 | 9 | 82 |
| Foam, a splash or a wake | 20 | 5% | 1 | 0 | 0 | 102 |
| An unclear object | 19 | 8% | 1 | 3 | 1 | 105 |
| A person on land | 15 | 6% | 2 | 2 | 1 | 60 |
| Empty water | 2 | 35% | 2 | 2 | 2 | 31 |

For comparison, the 1,652 flags on people that Ember kept include 98 pushed in by the photo's edge, 77 with the person more than a quarter of the crop from centre, and 284 with several people in the crop.

## How it was done

- A flag sits on a person when its centre is inside a labelled person box, the match `probe/score.py` uses. Where several boxes contain it, the smallest is taken.
- The crop is the one `probe/flag_check.py` sent: a square three times the flag's longer side, at least 96 pixels, moved inward where it would cross the photo's edge, shown to Ember at 224 pixels.
- The reason comes from Ember's words by the keyword rules in `reason()`, tried in a fixed order. `dismissed.json` lists all 210 with their words, so the sorting can be checked by eye. A few sit in the wrong pile: one person lying on sand is under "unclear object" because Ember's words did not mention sand.
- The two takes of the live clip cover the same 120 seconds, so their dismissals overlap.
- Counts differ slightly from earlier notes (93 lost on the first 300 frames, of which the check dropped 35) because those came from the scorecard, which keeps five marks a photo. This analysis counts every flag.

## Files

| File | What it holds |
|---|---|
| `sort_dismissed.py` | The analysis. `--sheets` also writes the example images and needs the MOBDrone photos linked in locally. |
| `summary.json` | Counts per run and reason, and the crop measurements for kept and dismissed flags |
| `dismissed.json` | All 210 dismissed flags: run, frame, box, both confidences, Ember's words, reason and measurements |
| `examples-*.jpg` | Up to eight MOBDrone crops per reason as Ember saw them, enlarged, with the labelled person outlined and Ember's words below |

Example crops are from MOBDrone (Cafarelli et al., 2022, [doi:10.5281/zenodo.5996890](https://doi.org/10.5281/zenodo.5996890), CC BY 4.0). AFO's photos are not in the repository.
