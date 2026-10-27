#!/usr/bin/env bash
N="${1:-5}"
MODEL="qwen/qwen3.8-27b"
URL="https://api.groq.com/openai/v1"

for i in $(seq 1 "$N"); do
  (cd moulinette && env PYTHONPATH=. uv run moulinette_eval dump mbpp --output "../cache/t$i.json" > /dev/null)
  uv run python -m agent_mbpp --task-file "cache/t$i.json" --output "cache/s$i.json" \
    --model-name "$MODEL" --provider-url "$URL" > /dev/null 2>&1
  (cd moulinette && env PYTHONPATH=. uv run moulinette_eval validate mbpp "../cache/t$i.json" "../cache/s$i.json" 2>&1 | grep -E "Task ID|Overall")
done
