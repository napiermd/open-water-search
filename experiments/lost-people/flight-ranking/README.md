# Which MOBDrone flights are hard for the detector

A free ranking made on November 24, 2026 for the map [Get the lost people back](https://github.com/napiermd/open-water-search/issues/29). It read no label and made no Ember call. Its purpose is to name harder flights for a test of the vote across seconds, since the only flight tested so far turned out to be one of the easiest.

## What was done

1. `cut_flights.py` cut all 66 MOBDrone videos into one frame per second, the way the search tool cuts a flight. That gave 4,211 seconds, about 70 minutes.
2. The detector ran over every second at 0.05 confidence, the setting the search tool uses. It raised 9,538 flags (`flags-005/`).
3. `rank_flights.py` linked flags from second to second with the search record's merge rule and counted three signs of trouble in each video:
   - **Unsure flags.** Flags under 0.25 confidence, the detector's published setting. 2,463 in all.
   - **One-second flags.** Flags that link to no other second. 679 in all.
   - **Lost seconds.** Seconds inside a track where the detector raised no flag for it. 345 in all.

Videos are ranked by trouble per minute: the three signs added up, each flag counted once, divided by the video's length.

## What it shows

**The live clip came from nearly the easiest flight in the set.** Its video, `DJI_0915_0007_40`, ranks 64th of 66 with 0.7 trouble per minute. The shortlisted flights below run from 62 to 174.

**The hard flights are the high ones.** Thirteen of the top fifteen were flown at 50 or 60 metres. People are a few pixels across, the seabed shows through as dark patches, and some frames hold a dozen flags.

**No long stretch of MOBDrone is untouched under the two-second rule.** The two earlier 300-frame samples were spread across every video. 2,205 of the 4,211 seconds lie within two seconds of a frame an earlier run scored, and the longest stretch clear of them is 41 seconds. Only 27 seconds outside the live clip are the very frame an earlier run scored. A whole-flight test therefore has to include seconds near earlier frames, and should report its result both on every second and on the seconds no earlier run came near.

## Shortlist

Every video of 45 seconds or more with at least 60 trouble per minute, leaving out the live clip's video. Both lines were set after seeing the flags and before reading any label of these seconds.

| Rank | Video | Seconds | Height | Flags | Unsure flags | One-second flags | Lost seconds | Trouble per minute | Tracks of 4 s or more | Seconds near an earlier frame |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | DJI_0915_0028_60m | 60 | 60 m | 299 | 154 | 19 | 19 | 174.0 | 26 | 41 |
| 10 | DJI_0915_0017_60m | 50 | 60 m | 331 | 63 | 3 | 13 | 91.2 | 24 | 38 |
| 11 | DJI_0804_0012_50m_3 | 60 | 50 m | 156 | 73 | 24 | 7 | 81.0 | 12 | 37 |
| 13 | DJI_0915_0027_50m | 67 | 50 m | 188 | 77 | 10 | 11 | 78.8 | 13 | 38 |
| 14 | DJI_0915_0023_50m | 73 | 50 m | 382 | 78 | 7 | 16 | 78.1 | 27 | 38 |
| 15 | DJI_0804_0017_40m | 53 | 40 m | 104 | 55 | 20 | 9 | 74.7 | 10 | 33 |
| 16 | DJI_0915_0015_50m | 178 | 50 m | 895 | 183 | 26 | 32 | 74.5 | 69 | 32 |
| 18 | DJI_0804_0018_40m | 79 | 40 m | 146 | 75 | 37 | 12 | 70.6 | 9 | 38 |
| 19 | DJI_0804_0010_60m | 56 | 60 m | 107 | 53 | 24 | 10 | 69.6 | 10 | 34 |
| 20 | DJI_0915_0019_60m | 62 | 60 m | 238 | 61 | 2 | 8 | 66.8 | 19 | 36 |
| 21 | DJI_0915_0003_50m | 88 | 50 m | 330 | 87 | 9 | 7 | 64.1 | 17 | 40 |
| 22 | DJI_0915_0018_60m | 113 | 60 m | 202 | 102 | 14 | 17 | 63.2 | 18 | 39 |
| 23 | DJI_0804_0009_40m | 63 | 40 m | 113 | 54 | 30 | 8 | 61.9 | 7 | 37 |
| 64 | DJI_0915_0007_40 (the live clip's video, for comparison) | 180 | 40 m | 159 | 1 | 2 | 0 | 0.7 | 6 | 151 |

The 13 shortlisted flights add up to 1,002 seconds and 3,491 flags. At the sealed runs' average of about $0.00004 a flag, checking every flag once would cost about $0.14.

Eleven videos with as much trouble are shorter than 45 seconds and are left out, because a vote across seconds needs a flight long enough to have tracks. `ranking.json` has every video.

## Limits

- Trouble per minute measures how unsure and unsteady the detector is. It cannot see people the detector never flags, so a flight could be hard in a way this ranking misses.
- The ranking says nothing about how Ember's check behaves on these flights.
- The three signs are added with equal weight. `ranking.json` holds each count, so the videos can be ranked another way.

## Files

| File | What it holds |
|---|---|
| `cut_flights.py` | Cuts every video into seconds and writes `inputs/manifest.json` |
| `inputs/manifest.json` | All 4,211 seconds: video, second, the video frame it kept, size and SHA-256 |
| `flags-005/` | The detector's `boxes.json` at 0.05 confidence and its `seal.json` |
| `rank_flights.py` | Links the flags, counts the trouble, marks the seconds earlier runs used, and writes `ranking.json` |
| `ranking.json` | Every video's counts, rank and shortlist mark, with the settings used |

To run it again, with MOBDrone fetched by `probe/fetch_mobdrone.py` and the detector set up as in `detector/README.md`:

~~~
python experiments/lost-people/flight-ranking/cut_flights.py DATA_DIR SECONDS_DIR
detector-venv/bin/python detector/run_detector.py experiments/lost-people/flight-ranking/inputs/manifest.json experiments/lost-people/flight-ranking/flags-005 --min-confidence 0.05
python3 experiments/lost-people/flight-ranking/rank_flights.py
~~~

MOBDrone is by Cafarelli et al., 2022, [doi:10.5281/zenodo.5996890](https://doi.org/10.5281/zenodo.5996890), CC BY 4.0. Its frames are not in the repository.

## Which stretches can support a vote?

[Eligible segments](eligible-segments.json) lists the inclusive start and end second of each stretch, its candidate count and the count of candidates with three eligible seconds on both sides. Generate it with `python3 experiments/lost-people/flight-ranking/eligible_segments.py`. The script reads the saved detector outputs and earlier sample frame numbers. It uses the same 60-source-frame exclusion as the ranking and requires consecutive eligible seconds in the same clip.

Of 1,002 shortlisted seconds, 521 qualify in 93 stretches across 13 previously sampled clips. They contain 1,842 detector flags. Only 155 seconds have the full seven-second context. Of those, 104 come from `DJI_0915_0015_50m`. This is a footage inventory. It contains no swimmer labels or Ember results.
