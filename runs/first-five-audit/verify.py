"""Verify the First Five replay against the sealed audit and recompute its result."""

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys


SEALED_REFERENCE_SHA256 = "87ce2b16fdac86262f83ec06b6a7af3eaa5455bcebd74c848cd0cf08e825e8be"
ARMS = ("ember", "detector")
OPENING_FIELDS = ("second", "x", "y", "time", "identity", "checked", "track", "identity_switches")
METRICS = ("reach_gain_pp", "empty_reduction_pct", "ember_reach_pct", "detector_reach_pct")
FAMILIES = 42
DRAWS = 20_000


def sha(data):
    return sha256(data).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_replay(replay, reference):
    require(replay["schema"] == 1, "Unsupported replay schema")
    windows = replay["windows"]
    require(len(windows) == len(reference["windows"]), "Sealed window count mismatch")
    for window, sealed in zip(windows, reference["windows"]):
        video, start, family = (window[key] for key in ("video", "start", "family"))
        where = f"{video} @ {start}s"
        require((video, start, family) == (sealed["video"], sealed["start"], sealed["family"]),
                f"Sealed window order or identity mismatch: {where}")
        require(digest(window["settings"]) == sealed["settings_sha256"],
                f"Sealed setting grades mismatch: {where}")
        require(set(window["arms"]) == set(ARMS), f"Sealed arms mismatch: {where}")
        for arm in ARMS:
            actual, expected = window["arms"][arm], sealed["arms"][arm]
            require(isinstance(actual, list), f"Opening queue must be an array: {where} / {arm}")
            require(len(actual) == len(expected), f"Sealed opening count mismatch: {where} / {arm}")
            for rank, (opening, signature) in enumerate(zip(actual, expected), 1):
                require(set(opening) == set(OPENING_FIELDS),
                        f"Sealed opening fields mismatch: {where} / {arm} / slot {rank}")
                values = [opening[key] for key in OPENING_FIELDS]
                require(digest([video, start, arm, rank, *values]) == signature,
                        f"Sealed opening mismatch: {where} / {arm} / slot {rank}")


def score(windows):
    paired = Counter()
    families = defaultdict(Counter)
    arms = {arm: Counter(in_water_reached=0, empty_openings=0, repeat_openings=0, identity_switches=0)
            for arm in ARMS}
    openings = 0
    for window in windows:
        scores = families[window["family"]]
        water = {int(track) for track, grade in window["settings"].items() if grade == "In water"}
        reached = {}
        for arm in ARMS:
            cards = window["arms"][arm]
            tracks = {card["track"] for card in cards} - {None}
            empty = sum(card["track"] is None for card in cards)
            reached[arm] = tracks & water
            arms[arm].update(
                in_water_reached=len(reached[arm]),
                empty_openings=empty,
                repeat_openings=len(cards) - empty - len(tracks),
                identity_switches=sum(card["identity_switches"] for card in cards),
            )
            scores[arm + "_empty"] += empty
            openings += len(cards)
        ember, detector = reached["ember"], reached["detector"]
        breakdown = {
            "both": len(ember & detector),
            "ember_only": len(ember - detector),
            "detector_only": len(detector - ember),
            "neither": len(water - ember - detector),
        }
        paired.update(breakdown)
        scores.update(breakdown)
    return openings, arms, paired, families


def measures(both, ember_only, detector_only, neither, ember_empty, detector_empty):
    water = both + ember_only + detector_only + neither
    return (
        100 * (ember_only - detector_only) / water,
        100 * (detector_empty - ember_empty) / detector_empty,
        100 * (both + ember_only) / water,
        100 * (both + detector_only) / water,
    )


def quantile(sorted_values, probability):
    position = (len(sorted_values) - 1) * probability
    lower = int(position)
    return sorted_values[lower] + (position - lower) * (sorted_values[lower + 1] - sorted_values[lower])


def intervals(families, weights):
    fields = ("both", "ember_only", "detector_only", "neither", "ember_empty", "detector_empty")
    rows = [families[name] for name in sorted(families)]
    columns = [[row[field] for row in rows] for field in fields]
    require(len(rows) == FAMILIES and len(weights) == FAMILIES * DRAWS,
            "Sealed family/bootstrap dimensions mismatch")
    estimates = measures(*(sum(column) for column in columns))
    draws = []
    for offset in range(0, len(weights), FAMILIES):
        sample = weights[offset:offset + FAMILIES]
        totals = [sum(n * count for n, count in zip(sample, column)) for column in columns]
        draws.append(measures(*totals))
    results = {}
    for name, estimate, values in zip(METRICS, estimates, zip(*draws)):
        ordered = sorted(values)
        results[name] = {
            "estimate": estimate,
            "interval_95": [quantile(ordered, 0.025), quantile(ordered, 0.975)],
        }
    return results


def verify(directory):
    reference_bytes = (directory / "sealed-reference.json").read_bytes()
    require(sha(reference_bytes) == SEALED_REFERENCE_SHA256, "Sealed reference checksum mismatch")
    reference = json.loads(reference_bytes)
    weights = (directory / "bootstrap-weights.bin").read_bytes()
    require(sha(weights) == reference["bootstrap_sha256"], "Sealed bootstrap checksum mismatch")
    replay = json.loads((directory / "replay.json").read_bytes())
    check_replay(replay, reference)
    windows = replay["windows"]
    openings, arms, paired, families = score(windows)
    return {
        "integrity": "All openings and setting grades match the independently sealed reference.",
        "windows": len(windows),
        "families": len(families),
        "openings": openings,
        "in_water_appearances": sum(paired.values()),
        "paired_in_water": paired,
        "arms": arms,
        "metrics": intervals(families, weights),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(verify(Path(__file__).resolve().parent), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.exit(f"Verification failed: {error}")
