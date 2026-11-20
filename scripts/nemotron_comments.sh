#!/usr/bin/env bash
# Nemotron on the 6 exam-pool tasks, x rounds.
MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b
URL=https://integrate.api.nvidia.com/v1
N=nemotron-3.5-super-120b
TASKS=(django__django-11066 sympy__sympy-13480 pydata__xarray-4629 scikit-learn__scikit-learn-13439 sympy__sympy-14711 sympy__sympy-18189)
DEST=cache/rep_nemotron_minipath4
mkdir -p "$DEST"
for round in 1 2 3 4 5 6; do
  for id in "${TASKS[@]}"; do
    MODEL=$MODEL URL=$URL MOUL_DIR=../moulinette bash scripts/eval_swebench.sh "$id" | grep -v '^PASSED' \
      | sed "s/^/$N minipath4 round $round: /" | tee -a "$DEST/summary.log"
    cp cache/swe_run/"$id".solution.json "$DEST/${N}__${id##*__}__minipath4-run${round}.json"
  done
done
echo; grep -c ': PASS' "$DEST/summary.log"