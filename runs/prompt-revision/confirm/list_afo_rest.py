"""List the AFO test-split photos the AFO test did not use, for confirming the revised prompt.

    python runs/prompt-revision/confirm/list_afo_rest.py DATA_DIR

DATA_DIR holds test.txt from the AFO release. Writes frames.json beside this script, in the layout of
runs/verify-afo/frames.json, with every test-split photo not in that file. No image and no label is read.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
USED = HERE.parents[1] / "verify-afo" / "frames.json"


def main(data):
    out = HERE / "frames.json"
    if out.exists():
        raise SystemExit(f"{out} already exists.")
    used = json.loads(USED.read_text())
    taken = {frame["image"] for frame in used["frames"]}
    rest = [name for name in sorted((data / "test.txt").read_text().split()) if name not in taken]
    out.write_text(json.dumps(dict(
        dataset=used["dataset"], source=used["source"], license=used["license"],
        split="test.txt", split_sha256=used["split_sha256"],
        selection=dict(method="Every test-split photo not in runs/verify-afo/frames.json.",
                       excluded_list_sha256=hashlib.sha256(USED.read_bytes()).hexdigest()),
        frames=[dict(clip=Path(name).stem.rsplit("_", 1)[0], image=name) for name in rest],
    ), indent=2) + "\n")
    print(f"{len(rest)} photos")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
