"""Seal the search record of a paid run, and write public copies without Meta's response and message IDs.

    python3 probe/seal_record.py RESULTS_DIR

seal.json records the SHA-256 of search-record.json and calls.jsonl exactly as the command wrote them, with the
model, settings, spend and ending. The redacted copies keep everything else, including Ember's raw answers and
token usage. Run this once, right after the run, then publish RESULTS_DIR without the two original files.
"""
import hashlib
import json
import sys
from pathlib import Path


def strip_ids(value):
    """Remove response.id and output[].id wherever a Meta response appears."""
    if isinstance(value, dict):
        response = value.get("response")
        if isinstance(response, dict):
            response.pop("id", None)
            for item in response.get("output", []):
                item.pop("id", None)
        for child in value.values():
            strip_ids(child)
    elif isinstance(value, list):
        for child in value:
            strip_ids(child)
    return value


def main(results):
    record_bytes = (results / "search-record.json").read_bytes()
    calls_bytes = (results / "calls.jsonl").read_bytes()
    record = json.loads(record_bytes)
    redacted_record = json.dumps(strip_ids(record), indent=2).encode()
    redacted_calls = b"".join(json.dumps(strip_ids(json.loads(line))).encode() + b"\n" for line in calls_bytes.splitlines() if line.strip())
    (results / "search-record-redacted.json").write_bytes(redacted_record)
    (results / "calls-redacted.jsonl").write_bytes(redacted_calls)
    (results / "seal.json").write_text(json.dumps(dict(
        search_record_sha256=hashlib.sha256(record_bytes).hexdigest(),
        calls_sha256=hashlib.sha256(calls_bytes).hexdigest(),
        search_record_redacted_sha256=hashlib.sha256(redacted_record).hexdigest(),
        calls_redacted_sha256=hashlib.sha256(redacted_calls).hexdigest(),
        removed="response.id and output[].id from every call",
        settings=record["settings"],
        spent_nanodollars=record["spent_nanodollars"],
        ending=record["ending"],
        calls=len(record["calls"]),
    ), indent=2))
    print(f"sealed {results}: {len(record['calls'])} calls, {record['spent_nanodollars'] / 1e9:.4f} dollars")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
