#!/usr/bin/env bash
# Usage (from the repo root): bash scripts/eval_swebench.sh [INSTANCE_ID...]
# When moulinette is outside the repo: MOUL_DIR=../moulinette bash scripts/eval_swebench.sh
# Runs and validates each SWE-bench task; defaults to the 3 benchmark tasks.
# On the school computers, run it inside rootlesskit bash.

IDS=("$@")
if [ ${#IDS[@]} -eq 0 ]; then
	IDS=(pydata__xarray-4629 sympy__sympy-13480 sympy__sympy-14711 django__django-11066 scikit-learn__scikit-learn-13439 sympy__sympy-18189)
fi
MODEL="${MODEL:-gemini-3.1-flash-lite}"
URL="${URL:-https://generativelanguage.googleapis.com/v1beta/openai}"
ROOT="$PWD"
OUT="$ROOT/cache/swe_run"
MOUL_DIR="${MOUL_DIR:-$ROOT/moulinette}"
MOUL=(env PYTHONPATH="$MOUL_DIR" uv run --directory "$MOUL_DIR" --python 3.12 moulinette_eval)

mkdir -p "$OUT"
passed=0
for id in "${IDS[@]}"; do
  task="$OUT/$id.task.json"
  sol="$OUT/$id.solution.json"
  rm -f "$sol"
  "${MOUL[@]}" dump swebench -t "$id" -o "$task" > /dev/null 2>&1
  "${MOUL[@]}" run-agent 900 "uv run --directory $ROOT python -m agent_swebench --task-file $task --output $sol --model-name $MODEL --provider-url $URL" > "$OUT/$id.run.log" 2>&1
  left=$(docker ps --format '{{.Image}}' | grep -c sweb.eval)
  if [ ! -f "$sol" ]; then
    echo "$id: NO SOLUTION (containers left: $left)"
    continue
  fi
  "${MOUL[@]}" validate swebench "$task" "$sol" > "$OUT/$id.val.log" 2>&1
  if grep -q "Overall.*PASSED" "$OUT/$id.val.log"; then
    passed=$((passed + 1))
    echo "$id: PASS (containers left: $left)"
  else
    echo "$id: FAIL (containers left: $left)"
  fi
done
echo "PASSED: $passed / ${#IDS[@]}"
