#!/usr/bin/env bash
# Usage: bash scripts/bench_model.sh MODEL URL TASK_ID [TASK_ID...]
# Runs each SWE-bench task with one model and keeps only that model's files
# in cache/bench_runs/<model>/ (no leftovers from other models).
MODEL="$1"; URL="$2"; shift 2
NAME=$(echo "$MODEL" | tr '/' '_')
DEST="cache/bench_runs/$NAME"
mkdir -p "$DEST"
for id in "$@"; do
  MODEL="$MODEL" URL="$URL" MOUL_DIR="${MOUL_DIR:-../moulinette}" \
    bash scripts/eval_swebench.sh "$id" | tee -a "$DEST/summary.log"
  cp cache/swe_run/"$id".* "$DEST"/
done
grep "PASS\|FAIL" "$DEST/summary.log"