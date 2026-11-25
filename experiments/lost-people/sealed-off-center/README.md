# Sealed off-center replay

Keep the current check. The frozen rule restored zero pins on the two preassigned 24-second replacement clips. Both rules found two tracks with one false pin in one episode. The gate required at least one correct restoration and zero added false pins. The [result](result.json) records both arms by clip and combined.

The replay used cached Ember descriptions and the existing flight scorer, with each original detector pin scored at its recorded second. The scorer sets aside labels without a track ID and uses the empty land exclusion list from the reference replay. No model or network calls were made. The public result identifies clips by kind.

From the repository root, provide the local research checkout, sealed artifact directory, and MOBDrone person annotations.

```sh
python3 -B experiments/lost-people/sealed-off-center/replay_off_center.py \
  --research-repo "$research_repo" \
  --artifacts "$sealed_artifacts" \
  --annotations "$mobdrone_annotations"
```

The research checkout needs `experiments/takeover-final/replay_off_center.py` with the frozen SHA-256 in the script and the original pilot scorer from commit `d6f29fe2ea86f38b02e7f0eb69adb3c69688577a`. The sealed artifact directory contains `locked-24s/` and `quote-only-24s/`. The replay verifies the reference, scorer sources, receipt, locked window list, both selected Ember queues, and annotations before scoring. A restoration is identified by its zero-based clip second and original zero-based flag index.

Run the focused tests against the same research checkout.

```sh
OWS_RESEARCH_REPO="$research_repo" \
  python3 -B experiments/lost-people/sealed-off-center/test_replay.py
```
