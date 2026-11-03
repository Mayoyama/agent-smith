#!/usr/bin/env bash
# Usage (from the repo root): bash scripts/eval_mbpp.sh [N] [TASK_ID...]
# Runs N tasks; the given TASK_IDs come first, the rest are random.
N="${1:-5}"
shift
IDS=("$@")
MODEL="qwen/qwen3.8-27b"
URL="https://api.groq.com/openai/v1"
ROOT="$PWD"
MOUL=(env PYTHONPATH="$ROOT/moulinette" uv run --directory "$ROOT/moulinette" --python 3.12 moulinette_eval)

mkdir -p "$ROOT/cache"
passed=0
for i in $(seq 1 "$N"); do
  id_arg=()
  if [ -n "${IDS[$((i - 1))]}" ]; then
    id_arg=(--task-id "${IDS[$((i - 1))]}")
  fi
  rm -f "$ROOT/cache/s$i.json"
  "${MOUL[@]}" dump mbpp "${id_arg[@]}" --output "$ROOT/cache/t$i.json" > /dev/null
  "${MOUL[@]}" run-agent 120 "uv run --directory $ROOT python -m agent_mbpp --task-file $ROOT/cache/t$i.json --output $ROOT/cache/s$i.json --model-name $MODEL --provider-url $URL" 2>&1 | grep -E "Agent (finished|exited|exceeded)"
  if [ ! -f "$ROOT/cache/s$i.json" ]; then
    echo "t$i: no solution.json"
    continue
  fi
  out=$("${MOUL[@]}" validate mbpp "$ROOT/cache/t$i.json" "$ROOT/cache/s$i.json" 2>&1)
  echo "$out" | grep -E "Task ID|Time:|Overall"
  if echo "$out" | grep -q "Overall.*PASSED"; then
    passed=$((passed + 1))
  fi
done
echo "PASSED: $passed / $N"
