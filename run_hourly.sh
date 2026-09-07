#!/bin/bash
# floatwatch hourly runner.
# The concentration series CANNOT be backfilled — a missed hour is permanently
# missing — so this is deliberately tolerant: each stage runs even if the last
# one failed, and everything is appended to logs rather than overwritten.
cd "$(dirname "$0")" || exit 1
PY=/opt/homebrew/bin/python3
[ -x "$PY" ] || PY=$(command -v python3) || exit 1
mkdir -p logs reports snapshots
STAMP=$(date -u +%FT%H)
{
  echo "=== $STAMP UTC ==="
  "$PY" collect.py 2>&1
  "$PY" report.py  2>&1 | tee "reports/$STAMP.txt"
  "$PY" check.py   2>&1 | tee "reports/paper-$STAMP.txt"
  # Hourly premium snapshot. The 13:00 and 14:00 UTC runs straddle the 09:30 ET
  # cash open, so this accumulates the pre/post-open pairs needed to answer the
  # convergence question across many sessions rather than one.
  "$PY" premium.py --record 2>&1
} >> logs/run.log 2>&1
