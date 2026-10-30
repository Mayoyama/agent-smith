# Benchmark Report

> DRAFT v3. Items marked **TODO** are not written yet. Each cell is a single
> run, so there is no variance estimate.

## 1. Setup

**Agent**: `agent_swebench` (Thought → Code → Observation loop, MCP tools
running in the task's Docker container). Same prompt, tools and limits for
every run: 30 iterations, 300,000 input tokens, 10,000 output tokens, 900 s,
400 tokens max per model reply.

**Providers / models**

| Provider | Model | Status |
|---|---|---|
| Mistral | `codestral-latest` | benchmarked |
| Mistral | `ministral-14b-latest` | benchmarked |
| Mistral | `ministral-8b-latest` | benchmarked |
| Mistral | `ministral-3b-latest` | benchmarked |
| Google (Gemini) | `gemini-3.1-flash-lite` | benchmarked |

Tried and excluded:
- `mistral-large-4`: reasoning model. Its answer comes back as a list of
  blocks. In `bench/mistral-large-4__sympy-13480.json` the reply text was
  empty at step 1, then the request failed with HTTP 400 at step 2. In a
  separate test, 399 of 400 tokens went into reasoning and the reply was cut
  (`finish_reason: length`). Cause of the 400 not established.
- `mistral-small-latest`, `mistral-medium-latest`: HTTP 429 with
  `x-ratelimit-limit-req-minute: 0` on our free-tier key, so no usable quota.
  The `mistral-small-latest` run ended with `all keys failed` and 0 iterations.
  Its file is not kept.
- `magistral-*`: not tried (reasoning models, same risk as `mistral-large-4`).

**Tasks** (SWE-bench Verified)

| Task | Repository | Bug |
|---|---|---|
| `sympy__sympy-13480` | sympy | typo `cotm` instead of `cothm` in `coth.eval` |
| `pydata__xarray-4629` | xarray | `merge(combine_attrs="override")` shares attrs with the first object |
| `sympy__sympy-14711` | sympy | `Vector + 0` raises `TypeError` |

Selection rationale: **TODO** (to be written by the authors).

**Validation**: every solution file is checked with `moulinette_eval validate
swebench` (correctness + metrics). Pass/Fail below is the moulinette result,
not the agent's own `success` field.

## 2. Results

| Model | Task | Pass | Iterations | Input tokens | Output tokens | Time (s) |
|---|---|---|---|---|---|---|
| codestral-latest | sympy-13480 | PASS | 6 | 17,755 | 197 | 24.9 |
| codestral-latest | xarray-4629 | PASS | 6 | 22,109 | 218 | 13.2 |
| codestral-latest | sympy-14711 | FAIL | 27 | 296,280 | 1,268 | 44.3 |
| ministral-14b-latest | sympy-13480 | PASS | 4 | 12,674 | 209 | 19.9 |
| ministral-14b-latest | xarray-4629 | PASS | 5 | 19,973 | 294 | 13.3 |
| ministral-14b-latest | sympy-14711 | PASS | 30 | 135,607 | 2,180 | 47.7 |
| ministral-8b-latest | sympy-13480 | PASS | 4 | 12,655 | 227 | 17.4 |
| ministral-8b-latest | xarray-4629 | PASS | 6 | 22,099 | 291 | 11.1 |
| ministral-8b-latest | sympy-14711 | PASS | 20 | 110,927 | 1,905 | 32.3 |
| ministral-3b-latest | sympy-13480 | PASS | 30 | 125,231 | 2,636 | 28.9 |
| ministral-3b-latest | xarray-4629 | PASS | 8 | 26,848 | 363 | 7.0 |
| ministral-3b-latest | sympy-14711 | FAIL | 30 | 170,185 | 2,265 | 29.3 |
| gemini-3.1-flash-lite | sympy-13480 | PASS | 6 | 27,917 | 505 | 37.9 |
| gemini-3.1-flash-lite | xarray-4629 | PASS | 9 | 36,953 | 1,180 | 37.0 |
| gemini-3.1-flash-lite | sympy-14711 | PASS | 21 | 104,308 | 2,621 | 44.2 |

Every row was validated with the moulinette on its own solution file.

Pass count: codestral 2/3, ministral-14b 3/3, ministral-8b 3/3, ministral-3b
2/3, gemini-3.1-flash-lite 3/3 (13 of 15 runs).

Notes
- Two runs have `success: false` (the agent never called `final_answer`) and
  still PASS: `ministral-14b-latest` on sympy-14711 (30 iterations) and
  `ministral-3b-latest` on sympy-13480 (30 iterations). The patch was taken
  from the repository diff by the `get_patch` fallback. The moulinette
  validates the patch whatever `success` says.
- `codestral-latest` on sympy-14711 stopped on `max_input_tokens` (296,280 of
  300,000) and its patch fails the tests.
- `ministral-3b-latest` repeated the same failing `edit_file` call many times
  despite a prompt rule forbidding it. On sympy-14711 its final patch is not
  valid Python.
- `ministral-8b-latest` passes sympy-14711, but its patch returns the vector
  for any `int`/`float`, not only `0`. It passes the task tests but is broader
  than the issue asks.
- On xarray-4629 and sympy-13480 the models give the same fix. Only
  sympy-14711 separates them.

## 3. Provider reliability

Computed from `steps[*].request_time_ms` and `steps[*].retries` of the files in
`bench/` (the 3 tasks per model).

| Model | Requests | Avg response time per request | Retries |
|---|---|---|---|
| codestral-latest | 39 | 866 ms | 0 |
| ministral-14b-latest | 39 | 1,349 ms | 0 |
| ministral-8b-latest | 30 | 1,161 ms | 0 |
| ministral-3b-latest | 68 | 857 ms | 0 |
| gemini-3.1-flash-lite | 36 | 2,685 ms | 0 |

Availability during the benchmark runs: 212 requests, 0 retries, no failed
request recorded. This covers the five benchmarked models only. Outside the
runs, `mistral-small-latest` and `mistral-medium-latest` returned 429 with a
limit of 0 requests per minute on our key, and `mistral-large-4` failed with
HTTP 400. Gemini free tier is limited to about 15 requests per minute, so the
runs were launched one at a time.

## 4. Intermediary metrics

Both measured by script from the `steps` of each solution file.

**4.1 Exploration efficiency.** First step whose code mentions the file of the
final patch (read, search or edit), and first `edit_file` call on that file
(successful or not). Order: sympy-13480 / xarray-4629 / sympy-14711.

| Model | First mention of the file | First edit |
|---|---|---|
| ministral-8b-latest | 1 / 1 / 1 | 2 / 4 / 13 |
| ministral-3b-latest | 1 / 2 / 1 | 2 / 3 / 5 |
| gemini-3.1-flash-lite | 1 / 3 / 1 | 2 / 6 / 8 |
| ministral-14b-latest | 1 / 2 / 2 | 2 / 3 / 27 |
| codestral-latest | 2 / 2 / 2 | 4 / 4 / 8 |

Every model reaches the right file within the first 3 steps, so exploration
does not separate them. The difference is on sympy-14711, between the first
mention and the first edit: step 27 for ministral-14b, 13 for ministral-8b,
5 to 8 for the others. The first edit of ministral-3b (step 5) is not
necessarily a successful one, and its final patch is invalid.

**4.2 Submission discipline.** Extra iterations between the first `run_tests()`
whose summary reports passed tests with no failure and the `final_answer`
iteration. 0 means the agent submits at once.

| Model | sympy-13480 | xarray-4629 | sympy-14711 |
|---|---|---|---|
| ministral-8b-latest | 0 | 0 | 0 |
| gemini-3.1-flash-lite | 2 | 0 | 0 |
| ministral-14b-latest | 0 | 0 | tests first pass at step 30, loop ended |
| codestral-latest | 0 | 0 | no passing test run |
| ministral-3b-latest | not detected | not detected | not detected |

When tests pass, the models submit right away, except gemini on sympy-13480
(2 extra iterations). ministral-14b saw its tests pass at step 30, the last
iteration, and had no step left to submit. For ministral-3b no passing test
run was detected in any of its 3 runs, including xarray-4629 where the run
is validated PASSED. We did not check whether it never called `run_tests()` or
whether the summary was truncated in the tool output.

## 5. Ablation study

**Change**: the `get_patch` fallback. When the loop ends without
`final_answer`, the agent submits the repository diff instead of an empty
solution.

**Method**: the fallback only acts after the loop has ended, so removing it
changes nothing in a run that ends with `final_answer`. For a run that ends
without one, the solution becomes empty. We therefore took the existing
traces and blanked the `solution` field, then validated the result with the
moulinette. We did not re-run the agent, so the comparison uses identical
traces.

| Run | With fallback | Without fallback |
|---|---|---|
| ministral-14b-latest, sympy-14711 | PASS | FAIL (validated with an empty solution) |
| ministral-3b-latest, sympy-13480 | PASS | FAIL (deduced, not validated) |

Over the 15 runs: 13 PASS with the fallback, 11 without. The other 13 runs
are unchanged: 11 end with `final_answer`, and 2 (codestral on sympy-14711,
ministral-3b on sympy-14711) fail either way.

Limit: this is a counterfactual on fixed traces. A real re-run could behave
differently because model output is not deterministic.

## 6. Conclusions

Preliminary, to be confirmed after sections 4 and 5.

- **Best candidate: `ministral-8b-latest`.** 3/3 on the tasks, and the fewest
  iterations and tokens on sympy-14711 among the models that pass it (20
  iterations, 110,927 input tokens), without relying on the fallback.
- **`gemini-3.1-flash-lite`**: 3/3 but slower per request (2.7 s vs about 1 s)
  and limited to about 15 requests per minute on the free tier.
- **`ministral-14b-latest`**: 3/3, but its sympy-14711 pass needed all 30
  iterations and the fallback.
- **Disregarded**: `mistral-large-4` (reasoning model, incompatible with the
  400-token reply cap), `mistral-small-latest` and `mistral-medium-latest` (no
  free quota on our key), `ministral-3b-latest` (loops on failed edits, 2/3,
  one invalid patch), `codestral-latest` (hits the input token cap on the
  hardest task).

## Reproducing

```
uv run python -m agent_swebench --task-file cache/swebench_task_<id>.json \
  --output bench/<model>__<task>.json --model-name <model> --provider-url <url>
```

The backing `solution.json` files are in `bench/`.
