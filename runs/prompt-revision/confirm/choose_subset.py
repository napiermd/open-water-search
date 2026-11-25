"""Choose the confirmation photos: a fixed-seed subset of the 214 untouched AFO photos sized to the $0.10 cap.

    python runs/prompt-revision/confirm/choose_subset.py

Reads the detector's flags (detector/candidates-005/afo-214/boxes.json), never the labels. Orders the 214 photos by
SHA-256 of seed/photo and takes them in that order while the expected cost of checking them with one prompt stays at
or under $0.042, from the per-request and per-crop prices of the sealed runs. Writes subset-boxes.json, the flags of
the chosen photos in the detector's layout, and subset.json, the list with the method.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "probe"))
import flag_check  # noqa: E402

SEED = "open-water-search-prompt-confirm-2026-11-24"
PER_REQUEST, PER_CROP, LIMIT = 6.27e-5, 2.9e-5, 0.042


def main():
    photos = json.loads((ROOT / "detector/candidates-005/afo-214/boxes.json").read_text())
    order = sorted(photos, key=lambda p: hashlib.sha256(f"{SEED}/{p['frame']}".encode()).hexdigest())
    chosen, total = [], 0.0
    for photo in order:
        flags = len(flag_check.candidates(photo))
        cost = (PER_REQUEST if flags else 0) + PER_CROP * flags
        if total + cost > LIMIT:
            break
        chosen.append(photo)
        total += cost
    (HERE / "subset-boxes.json").write_text(json.dumps(chosen))
    (HERE / "subset.json").write_text(json.dumps(dict(
        seed=SEED, photos=[p["frame"] for p in chosen], flags=sum(len(flag_check.candidates(p)) for p in chosen),
        expected_cost_per_prompt=round(total, 4), method=__doc__.split("\n\n")[1].strip()), indent=2) + "\n")
    print(len(chosen), "photos,", round(total, 4), "expected per prompt")


if __name__ == "__main__":
    main()
