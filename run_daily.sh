#!/bin/bash
# Daily floatwatch snapshot. The series cannot be backfilled — a missed day is
# permanently missing, so prefer over-running to under-running.
cd "$(dirname "$0")"
python3 collect.py >> logs/collect.log 2>&1
python3 report.py  >  reports/$(date -u +%F).txt 2>&1
