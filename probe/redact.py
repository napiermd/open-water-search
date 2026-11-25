"""Write a public copy of a sealed trace with Meta's response and message IDs removed.

    python redact.py live
    python redact.py experiments/zoom-first/validation-30/live

Everything else, including Ember's raw text answers and token usage, is kept as returned. redaction.json
records the SHA-256 of the original trace, which matches seal.json, and of the redacted copy.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def strip_ids(record):
    response = record["evidence"]["response"]
    response.pop("id", None)
    for item in response["output"]:
        item.pop("id", None)
    return record


def main(folder):
    live = ROOT / folder
    original = (live / "trace.json").read_bytes()
    seal = json.loads((live / "seal.json").read_text())
    if hashlib.sha256(original).hexdigest() != seal["sha256"]:
        raise SystemExit("trace.json does not match seal.json")
    redacted = json.dumps([strip_ids(r) for r in json.loads(original)], sort_keys=True).encode()
    (live / "trace-redacted.json").write_bytes(redacted)
    (live / "redaction.json").write_text(json.dumps(dict(
        original_sha256=seal["sha256"],
        redacted_sha256=hashlib.sha256(redacted).hexdigest(),
        removed="response.id and output[].id from every call",
    ), indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
