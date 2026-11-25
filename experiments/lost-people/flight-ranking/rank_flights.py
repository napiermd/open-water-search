"""Rank MOBDrone's videos by how hard each looks for the detector, from its flags alone.

    python3 experiments/lost-people/flight-ranking/rank_flights.py

Reads inputs/manifest.json (every second of every video, from cut_flights.py), flags-005/boxes.json (the detector's
boxes at 0.05 confidence or more, from detector/run_detector.py) and the frame lists of earlier runs. No label is read.

A second's flags are the ones the search tool would send to Ember: swimmer boxes, at most 12, most confident first.
Flags are linked from second to second by the search record's merge rule: a flag joins the nearest track last seen
one or two seconds earlier within 10% of the frame width.

For each video, ranking.json records:

- seconds, and the drone's height from the file name
- flags, and flags per minute
- unsure flags: under 0.25 confidence, the detector's published setting
- one-second flags: flags linked to no other second
- lost seconds: seconds inside a track where the detector did not flag it
- trouble per minute: unsure flags, one-second flags and lost seconds, each counted once, per minute of flight
- tracks, tracks lasting 4 seconds or more, and the longest track
- used seconds: seconds within 60 frames (about 2 seconds) of a frame an earlier run scored, and every second of the
  live clip's stretch. same_frame_seconds counts the seconds whose own frame an earlier run scored.
- the longest stretch of seconds no earlier run used

Videos are ranked by trouble per minute, most first. The shortlist is every video of 45 seconds or more with at least
60 trouble per minute. Both lines were set after seeing the flags and before reading any label of these seconds.
"""
import json
import re
import sys
from collections import Counter
from itertools import groupby
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "probe"))
from flag_check import candidates  # noqa: E402
from open_water_search import MERGE_DISTANCE, MERGE_SECONDS  # noqa: E402

UNSURE_BELOW = 0.25
NEAR_FRAMES = 60
LONG_TRACK = 4
SHORTLIST_SECONDS = 45
SHORTLIST_TROUBLE = 60
EARLIER_SAMPLES = ["mobdrone/frames.json", "runs/verify-mobdrone/frames.json"]
LIVE_CLIP = "mobdrone/clip/scoring-only/manifest.json"


def link(seconds, width):
    """Tracks of flags, by the merge rule in open_water_search.possible_people()."""
    tracks = []
    for second, flags in seconds:
        can_join = [track for track in tracks if 0 < second - track[-1]["second"] <= MERGE_SECONDS]
        for flag in sorted(flags, key=lambda f: -f["confidence"]):
            near = [track for track in can_join if distance(track[-1], flag) <= MERGE_DISTANCE * width]
            if near:
                track = min(near, key=lambda track: distance(track[-1], flag))
                can_join.remove(track)
            else:
                track = []
                tracks.append(track)
            track.append(flag)
    return tracks


def distance(first, second):
    return ((first["x"] - second["x"]) ** 2 + (first["y"] - second["y"]) ** 2) ** 0.5


def used_frames():
    """Per video, the frames earlier runs scored and the live clip's stretch as (first, last)."""
    scored, stretches = {}, {}
    for listing in EARLIER_SAMPLES:
        for frame in json.loads((ROOT / listing).read_text())["frames"]:
            scored.setdefault(frame["video"], []).append(frame["frame"])
    clip = json.loads((ROOT / LIVE_CLIP).read_text())["clip"]
    stretches[clip["video"]] = (clip["first_frame"], clip["first_frame"] + clip["frames"] - 1)
    return scored, stretches


def longest_free(used):
    """The longest run of unused seconds as (first second, length)."""
    best, start = (0, 0), None
    for second, taken in enumerate(used + [True]):
        if not taken and start is None:
            start = second
        if taken and start is not None:
            best = max(best, (start, second - start), key=lambda run: run[1])
            start = None
    return best


def main():
    rows = json.loads((HERE / "inputs" / "manifest.json").read_text())["frames"]
    boxes = {photo["frame"]: photo for photo in json.loads((HERE / "flags-005" / "boxes.json").read_text())}
    scored, stretches = used_frames()
    ranking = []
    for video, in_video in groupby(rows, key=lambda row: row["video"]):
        in_video = list(in_video)
        seconds = []
        for row in in_video:
            flags = [dict(second=row["second"], x=(b[0] + b[2]) / 2, y=(b[1] + b[3]) / 2, confidence=b[4])
                     for b in candidates(boxes[row["frame"]])]
            seconds.append((row["second"], flags))
        tracks = link(seconds, in_video[0]["width"])
        flags = [flag for _, in_second in seconds for flag in in_second]
        unsure = sum(flag["confidence"] < UNSURE_BELOW for flag in flags)
        alone = [track[0] for track in tracks if len(track) == 1]
        lost = sum(track[-1]["second"] - track[0]["second"] + 1 - len(track) for track in tracks)
        # A one-second flag under 0.25 is one piece of trouble, counted once.
        trouble = unsure + sum(flag["confidence"] >= UNSURE_BELOW for flag in alone) + lost
        first, last = stretches.get(video, (None, None))
        used = [any(abs(row["video_frame"] - frame) <= NEAR_FRAMES for frame in scored.get(video, []))
                or (first is not None and first - NEAR_FRAMES <= row["video_frame"] <= last + NEAR_FRAMES)
                for row in in_video]
        same_frame = sum(row["video_frame"] in scored.get(video, []) or (first is not None and first <= row["video_frame"] <= last)
                         for row in in_video)
        free_from, free_seconds = longest_free(used)
        minutes = len(in_video) / 60
        height = re.search(r"_(\d+)m?(_\d)?$", Path(video).stem)
        ranking.append(dict(
            video=video, seconds=len(in_video), height_m=int(height.group(1)) if height else None,
            flags=len(flags), flags_per_minute=round(len(flags) / minutes, 1),
            unsure_flags=unsure, one_second_flags=len(alone), lost_seconds=lost,
            trouble_per_minute=round(trouble / minutes, 1),
            tracks=len(tracks), long_tracks=sum(len(track) >= LONG_TRACK for track in tracks),
            longest_track_seconds=max((track[-1]["second"] - track[0]["second"] + 1 for track in tracks), default=0),
            seconds_with_flags=sum(bool(in_second) for _, in_second in seconds),
            most_flags_in_a_second=max((len(in_second) for _, in_second in seconds), default=0),
            used_seconds=sum(used), same_frame_seconds=same_frame,
            longest_unused_stretch=dict(first_second=free_from, seconds=free_seconds),
            in_live_clip=video in stretches))
    ranking.sort(key=lambda row: -row["trouble_per_minute"])
    for place, row in enumerate(ranking, 1):
        row["rank"] = place
        row["shortlist"] = (row["seconds"] >= SHORTLIST_SECONDS and row["trouble_per_minute"] >= SHORTLIST_TROUBLE
                            and not row["in_live_clip"])
    totals = Counter()
    for row in ranking:
        for key in ("seconds", "flags", "unsure_flags", "one_second_flags", "lost_seconds", "tracks", "used_seconds",
                    "same_frame_seconds"):
            totals[key] += row[key]
    short = [row for row in ranking if row["shortlist"]]
    shortlist = dict(videos=[row["video"] for row in short],
                     **{key: sum(row[key] for row in short) for key in ("seconds", "flags", "used_seconds", "same_frame_seconds")})
    (HERE / "ranking.json").write_text(json.dumps(dict(
        settings=dict(flag_confidence=0.05, unsure_below=UNSURE_BELOW, merge_seconds=MERGE_SECONDS,
                      merge_distance=MERGE_DISTANCE, near_frames=NEAR_FRAMES, long_track_seconds=LONG_TRACK,
                      shortlist_seconds=SHORTLIST_SECONDS, shortlist_trouble_per_minute=SHORTLIST_TROUBLE,
                      earlier_samples=EARLIER_SAMPLES, live_clip=LIVE_CLIP),
        totals=dict(videos=len(ranking), **totals), shortlist=shortlist, videos=ranking), indent=1) + "\n")
    print("| Rank | Video | Shortlist | Seconds | Height | Flags | Unsure flags | One-second flags | Lost seconds | "
          "Trouble per minute | Tracks of 4 s or more | Used seconds | Longest unused stretch |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in ranking:
        print(f"| {row['rank']} | {Path(row['video']).stem} | {'yes' if row['shortlist'] else ''} | {row['seconds']} | "
              f"{row['height_m']} m | {row['flags']} | {row['unsure_flags']} | {row['one_second_flags']} | {row['lost_seconds']} | "
              f"{row['trouble_per_minute']} | {row['long_tracks']} | {row['used_seconds']} | "
              f"{row['longest_unused_stretch']['seconds']} s |")
    print(dict(totals), shortlist)


if __name__ == "__main__":
    main()
