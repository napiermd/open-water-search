"""Build public records from local inputs and commitments from the previous audit kit."""

import argparse
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np

from verify import scored_frames


HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parents[1] / "pages" / "first-five"
AUDIT_SHA = "c4dcb6f6bb3fba21377f0b389697d1c571f4fb985642eb0dde33589bc9c043dd"
GRADES_SHA = "2ddab6f46d97331c46fad9e2e4ab9d0819b14fb5b058a1115bd349373ff9c59b"
ARMS = ("ember", "detector")


def require_seal(data, expected, name):
    if sha256(data).hexdigest() != expected:
        raise ValueError(f"Source seal mismatch: {name}")
    return data


def grades_by_window(data):
    windows = {}
    for row in csv.DictReader(StringIO(data.decode("utf-8"))):
        grades = windows.setdefault((row["video"], int(row["start"])), {})
        if row["track"] in grades:
            raise ValueError(f"Duplicate setting grade: {row}")
        grades[row["track"]] = row["setting"]
    return windows


def export_replay(audit, grades, frames):
    """Publish the original opening fields, preserving arm order and numeric values."""
    windows = []
    for window in audit:
        settings = grades.get((window["video"], window["start"]), {})
        if len(settings) != window["total"]:
            raise ValueError(f"Incomplete setting grades for {window['video']} @ {window['start']}")
        arms = {}
        for arm in ARMS:
            openings = []
            for card in window[arm]["cards"]:
                opening = card["opening"]
                source = frames[window["video"], opening["second"]]
                openings.append({
                    **opening, "identity_switches": card["switches_before"],
                    "native_frame": source["video_frame"], "jpeg_sha256": source["sha256"],
                })
            arms[arm] = openings
        windows.append({
            "video": window["video"],
            "start": window["start"],
            "family": window["family"],
            "settings": settings,
            "arms": arms,
        })
    return {"schema": 2, "windows": windows}


def commitment(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sealed_reference(kit_path, draws):
    """Read the previously distributed audit directly. Never read the exported replay."""
    with ZipFile(kit_path) as kit:
        audit = json.loads(require_seal(kit.read("primary-audit.json"), AUDIT_SHA, "sealed primary audit"))
        grades = grades_by_window(require_seal(kit.read("paired-grades.csv"), GRADES_SHA, "sealed grades"))
    windows = []
    for sealed in audit:
        key = sealed["video"], sealed["start"]
        arms = {}
        for arm in ARMS:
            arms[arm] = []
            for rank, card in enumerate(sealed[arm]["cards"], 1):
                pin = card["opening"]
                values = [
                    rank, pin["second"], pin["x"], pin["y"], pin["time"],
                    pin["identity"], pin["checked"], pin["track"], card["switches_before"],
                ]
                arms[arm].append(commitment([*key, arm, *values]))
        windows.append({
            "video": key[0],
            "start": key[1],
            "family": sealed["family"],
            "settings_sha256": commitment(grades.get(key, {})),
            "arms": arms,
        })
    return {
        "source_sha256": {"primary-audit.json": AUDIT_SHA, "paired-grades.csv": GRADES_SHA},
        "bootstrap_sha256": sha256(draws).hexdigest(),
        "windows": windows,
    }


def json_bytes(value):
    return (json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path, help="Directory holding the local water-probe outputs")
    root = parser.parse_args().source_root
    audit = root / "paced-flight/sighting-updates/archive/detector-control/primary-audit.json"
    grades = root / "queue-audit-129/hit-setting/paired-grades.csv"
    manifest = HERE.parents[1] / "experiments/lost-people/flight-ranking/inputs/manifest.json"
    manifest_bytes = manifest.read_bytes()
    replay = json_bytes(export_replay(
        json.loads(require_seal(audit.read_bytes(), AUDIT_SHA, audit.name)),
        grades_by_window(require_seal(grades.read_bytes(), GRADES_SHA, grades.name)),
        scored_frames(manifest_bytes),
    ))
    # These are the paired-evidence notebook's exact draws in lexicographic family order.
    weights = np.random.default_rng(20261126).multinomial(42, np.full(42, 1 / 42), size=20000)
    draws = weights.astype(np.uint8).tobytes()
    reference = json_bytes(sealed_reference(root / "share/water-statistics/audit.zip", draws))
    reference_sha = sha256(reference).hexdigest()
    verifier = (HERE / "verify.py").read_bytes()
    if f'SEALED_REFERENCE_SHA256 = "{reference_sha}"'.encode() not in verifier:
        raise ValueError(f"Verifier needs the independently generated reference seal: {reference_sha}")
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "replay.json").write_bytes(replay)
    with ZipFile(PUBLIC / "audit.zip", "w") as kit:
        for name, data in {
            "README.md": (HERE / "README.md").read_bytes(),
            "verify.py": verifier,
            "replay.json": replay,
            "sealed-reference.json": reference,
            "detector-inputs.json": manifest_bytes,
            "bootstrap-weights.bin": draws,
        }.items():
            kit.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)


if __name__ == "__main__":
    main()
