"""Check the rule that merges sightings into possible people against the labeled people of a MOBDrone clip.

    python probe/check_merge_rule.py SEARCH_RECORD SCORING_DIR

SEARCH_RECORD is written by open_water_search.py. SCORING_DIR is the clip's scoring-only folder written by
cut_mobdrone_clip.py: one YOLO label file per second, and labels/tracks.json with the MOBDrone track ID of each
labeled person, line by line. Prints a JSON report.

Who is who comes from MOBDrone's track IDs, and only as far as they reach:
- Boxes with the same track ID are the same person.
- Two track IDs labeled in the same second are two different people.
- Two track IDs never labeled in the same second may be one person who left the picture and came back under a new
  ID, so a possible person holding both is counted apart, as unknown.
- A box without a track ID has no known identity, and sightings on it are left out.

A sighting belongs to the labeled person whose box holds it, or the one whose box center is nearer when two boxes
hold it. A possible person joined two different people when it holds sightings of two people labeled in the same
second. A person was split when consecutive sightings of that person, in time order, belong to different possible
people. Splits after a gap of more than two seconds are what the rule does on purpose. Splits within two seconds
come from sightings too far apart, or from a second sighting of the person in one frame.
"""
import hashlib
import json
import math
import sys
from itertools import combinations
from pathlib import Path

from open_water_search import MERGE_SECONDS
from score import contains, groundtruth

AFTER_A_GAP = f"after_a_gap_of_more_than_{MERGE_SECONDS}_seconds"
WITHIN = f"within_{MERGE_SECONDS}_seconds"


def labeled_people(scoring, timeline):
    """Each frame's labeled people as [(track ID or None, box in pixels)]. Raises ValueError for a label file or
    tracks.json that differs from the manifest."""
    manifest = json.loads((scoring / "manifest.json").read_text())
    raw = (scoring / manifest["tracks"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["tracks_sha256"]:
        raise ValueError(f"{manifest['tracks']} does not match the manifest")
    tracks = json.loads(raw)
    return {frame: list(zip(tracks[frame], [box for _, box in boxes]))
            for frame, boxes in groundtruth(scoring, timeline).items()}


def holder(sighting, people):
    """The (track ID, box) whose box holds the sighting, the nearer-centered of two, or None when no box does."""
    point = (sighting["x"], sighting["y"])
    holding = [person for person in people if contains(point, person[1])]
    return min(holding, key=lambda person: math.dist(point, ((person[1][0] + person[1][2]) / 2,
                                                             (person[1][1] + person[1][3]) / 2)), default=None)


def check(record, people):
    together = set()
    for frame in people.values():
        tracks = sorted({track for track, _ in frame if track is not None})
        together.update(combinations(tracks, 2))
    sightings = dict(on_a_labeled_person=0, on_a_box_without_a_track_id=0, on_no_labeled_person=0)
    seen = {}
    joined_different = joined_unknown = 0
    by_possible_person = []
    for possible_person in record["possible_people"]:
        held = set()
        for sighting in possible_person["sightings"]:
            person = holder(sighting, people[sighting["frame"]])
            if person is None:
                sightings["on_no_labeled_person"] += 1
            elif person[0] is None:
                sightings["on_a_box_without_a_track_id"] += 1
            else:
                sightings["on_a_labeled_person"] += 1
                held.add(person[0])
                seen.setdefault(person[0], []).append((sighting["second"], possible_person["number"]))
        pairs = list(combinations(sorted(held), 2))
        if any(pair in together for pair in pairs):
            joined_different += 1
        elif pairs:
            joined_unknown += 1
        by_possible_person.append(dict(number=possible_person["number"],
                                       first_seen_second=possible_person["first_seen_second"],
                                       last_seen_second=possible_person["last_seen_second"],
                                       labeled_people=sorted(held)))
    splits = {AFTER_A_GAP: 0, WITHIN: 0}
    for track_sightings in seen.values():
        ordered = sorted(track_sightings)
        for (second, number), (next_second, next_number) in zip(ordered, ordered[1:]):
            if number != next_number:
                splits[AFTER_A_GAP if next_second - second > MERGE_SECONDS else WITHIN] += 1
    return dict(
        identity="MOBDrone track IDs: one ID is one person; IDs labeled in the same second are different people; "
                 "IDs never labeled together are unknown; boxes without an ID are left out",
        seconds=len(people),
        labeled_people=len({track for frame in people.values() for track, _ in frame if track is not None}),
        possible_people=len(record["possible_people"]),
        sightings=sightings,
        joined_two_different_people=joined_different,
        joined_people_never_labeled_together=joined_unknown,
        labeled_people_sighted=len(seen),
        labeled_people_split=sum(len({number for _, number in track_sightings}) > 1
                                 for track_sightings in seen.values()),
        splits=splits,
        by_possible_person=by_possible_person)


if __name__ == "__main__":
    record = json.loads(Path(sys.argv[1]).read_text())
    try:
        people = labeled_people(Path(sys.argv[2]), record["coverage_timeline"])
    except ValueError as error:
        sys.exit(str(error))
    print(json.dumps(check(record, people), indent=2))
