#!/bin/sh
set -eu
code=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
root=$(dirname "$code")
cd "$code"
# Leave system libraries and TLS roots readable. Neither answer keys nor other
# workspace datasets are within the inference process's data read allowlist.
profile='(version 1)
(allow default)
(deny file-read* (subpath (param "DOCS")) (subpath (param "DOWNLOADS")) (subpath (param "DESKTOP")))
(allow file-read* (subpath (param "CODE")) (subpath (param "INPUTS")) (subpath (param "LIVE")) (subpath (param "VALIDATION_INPUTS")) (subpath (param "VALIDATION_LIVE")))
(deny file-write* (subpath (param "DOCS")) (subpath (param "DOWNLOADS")) (subpath (param "DESKTOP")))
(allow file-write* (subpath (param "LIVE")) (subpath (param "VALIDATION_LIVE")))
(allow file-read-metadata)
(deny file-read* (subpath (param "LABELS")) (subpath (param "VALIDATION_LABELS")))'
exec /usr/bin/sandbox-exec -D "DOCS=$HOME/Documents" -D "DOWNLOADS=$HOME/Downloads" -D "DESKTOP=$HOME/Desktop" -D "CODE=$code" -D "INPUTS=$root/inputs" -D "LIVE=$root/live" -D "VALIDATION_INPUTS=$root/validation/inputs" -D "VALIDATION_LIVE=$root/validation/live" -D "LABELS=$root/scoring-only" -D "VALIDATION_LABELS=$root/validation/scoring-only" -p "$profile" "${PYTHON:-python3}" -B "$@"
