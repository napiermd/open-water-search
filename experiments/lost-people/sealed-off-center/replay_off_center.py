"""Replay the frozen off-center rule on the two sealed replacement clips."""
import argparse
import hashlib
import json
from pathlib import Path
from types import FunctionType

REFERENCE_SHA256 = "690277a6b0271c2c1b0ff7019d82e7d5dc8fd9dc687989d4b88d17188e7880c4"
PILOT_SCORER_SHA256 = "d4b65fa971336b82fe4bfc29fa466a43abb7ee62efacd6fe1e0ae49f0f7c44c2"
PHOTO_SCORER_SHA256 = "c3f3f296eb705576814b237ddd7c207de8f08f5ce5948e02ea2a9ee1769173e3"
RECEIPT_SHA256 = "82ff25b3884bd9edc8e436c057adf191c96de8ff936357e00380b2fdcb64ac9d"
ANNOTATIONS_SHA256 = "08b8050efec2972a98af831a17f691c09419674bc06e5876a5d004528cc2b0da"
WINDOW_SECONDS = 24
ARMS = {"current": "current", "restore_off_center": "padded"}


def checked_bytes(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"SHA-256 mismatch: {path}")
    return data


def load_reference(research_repo):
    reference = research_repo / "experiments/takeover-final/replay_off_center.py"
    source = checked_bytes(reference, REFERENCE_SHA256)
    checked_bytes(research_repo / "experiments/harder-pilot/score_pilot.py", PILOT_SCORER_SHA256)
    checked_bytes(research_repo / "probe/score.py", PHOTO_SCORER_SHA256)

    # Load the frozen predicate and its original scorer without running the primary replay.
    scope = {"__file__": str(reference), "__name__": "frozen_off_center"}
    exec(compile(source, str(reference), "exec"), scope)
    return scope["scorer"], scope["restore"]


def load_replacements(artifacts, receipt):
    windows_path = artifacts / "quote-only-24s/windows.json"
    windows = json.loads(checked_bytes(windows_path, receipt["input_hashes"]["windows.json"]))
    selected = [(n, window) for n, window in enumerate(windows, 1)
                if window["role"] == "replacement"]
    if (sorted(window["kind"] for _, window in selected) != ["empty", "positive"]
            or len({window["video"] for _, window in selected}) != 2):
        raise ValueError("Expected one empty and one positive locked replacement")

    replacements = {}
    for n, window in selected:
        name = f"queues/window-{n:02d}/ember.json"
        path = artifacts / "locked-24s" / name
        rows = json.loads(checked_bytes(path, receipt["queue_hashes"][name]))
        start = window["start"]
        if [(row["video"], row["second"]) for row in rows] != [
            (window["video"], second) for second in range(start, start + WINDOW_SECONDS)
        ]:
            raise ValueError(f"Queue does not cover the exact locked seconds: {name}")
        replacements[window["kind"]] = rows
    return replacements


def score_clip(rows, coco, scorer, restore):
    video = rows[0]["video"]
    frames, marks, added = [], [], []
    for row in rows:
        flags = [[*flag["box"], flag["detector_confidence"]] for flag in row["flags"]]
        frame = dict(row, block=video, flags=flags)
        frames.append(frame)
        for i, flag in enumerate(row["flags"]):
            mark = dict(frame=frame["frame"], i=i, delivery_second=frame["second"])
            if flag["kept"]:
                marks.extend(dict(mark, arm=arm) for arm in ARMS.values())
            elif restore(flag["description"]):
                marks.append(dict(mark, arm="padded"))
                added.append((frame, i))

    # Override only the pilot's clip allowlist, as in the frozen reference.
    load_truth = FunctionType(scorer.load_truth.__code__,
                              dict(scorer.load_truth.__globals__, VIDEOS={video}))
    truth, _ = load_truth(frames, coco, [])
    indexed = scorer.index_marks(frames, marks)
    scores = {name: scorer.score_arm(frames, truth, indexed, arm) for name, arm in ARMS.items()}

    restored_pins = []
    for frame, i in added:
        key = ("padded", frame["frame"])
        mark = next(mark for mark in indexed[key] if mark["i"] == i)
        # The same scorer can classify one pin, including a pin on a set-aside label.
        pin_score = scorer.score_arm([frame], truth, {key: [mark]}, "padded")
        pin = dict(clip_second=frame["second"] - rows[0]["second"], flag_index=i)
        if pin_score["false_marks"]:
            pin["disposition"] = "false"
        elif pin_score["ignored_marks"]:
            pin["disposition"] = "set_aside"
        else:
            (_, track), = scorer.found(pin_score)
            pin.update(disposition="correct", track_id=track)
        restored_pins.append(pin)

    current = scorer.found(scores["current"])
    candidate = scorer.found(scores["restore_off_center"])
    report = dict(seconds=len(rows), restored_pins=restored_pins,
                  new_tracks=sorted(track for _, track in candidate.keys() - current.keys()))
    for name, arm in ARMS.items():
        score = scores[name]
        pins = sum(mark["arm"] == arm for mark in marks)
        report[name] = dict(pins=pins,
                            correct_pins=pins - score["false_marks"] - score["ignored_marks"],
                            false_pins=score["false_marks"], set_aside_pins=score["ignored_marks"],
                            false_pin_seconds=score["false_mark_seconds"],
                            false_episodes=score["false_episodes"], tracks=score["identities"],
                            found=score["found"], missed=score["missed"])
    return report


def score_replacements(replacements, coco, scorer, restore):
    clips = {kind: score_clip(rows, coco, scorer, restore) for kind, rows in replacements.items()}
    combined = {"seconds": sum(clip["seconds"] for clip in clips.values())}
    for arm in ARMS:
        combined[arm] = {key: sum(clip[arm][key] for clip in clips.values())
                         for key in clips["empty"][arm]}
    current, candidate = combined["current"], combined["restore_off_center"]
    correct = candidate["correct_pins"] - current["correct_pins"]
    false = candidate["false_pins"] - current["false_pins"]
    passes = correct >= 1 and false == 0
    return dict(clips=clips, combined=combined,
                gate=dict(correctly_restored_pins=correct, added_false_pins=false, passes=passes),
                selection="restore_off_center" if passes else "current")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-repo", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    args = parser.parse_args()
    scorer, restore = load_reference(args.research_repo.resolve())
    receipt = json.loads(checked_bytes(args.artifacts / "locked-24s/receipt.json", RECEIPT_SHA256))
    replacements = load_replacements(args.artifacts, receipt)
    coco = json.loads(checked_bytes(args.annotations, ANNOTATIONS_SHA256))
    result = score_replacements(replacements, coco, scorer, restore)
    print(json.dumps(dict(reference_sha256=REFERENCE_SHA256, cached_model=receipt["model"],
                          cached_route=receipt["route"], model_calls=0, network_calls=0,
                          spend_usd=0, **result), indent=2))


if __name__ == "__main__":
    main()
