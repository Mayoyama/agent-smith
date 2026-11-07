# Benchmark Report

> Each cell is a single run, so there is no variance estimate.

## 1. Setup

**Agent**: `agent_swebench` (Thought → Code → Observation loop, MCP tools
running in the task's Docker container). Same prompt, tools and limits for
every run of sections 2 to 5: 30 iterations, 300,000 input tokens, 10,000
output tokens, 900 s, 400 tokens max per model reply. The 15 runs of section 2
were produced before the multi-format tool-call extraction (`agent/extract.py`)
was added to the agent, and were not re-run with it. Sections 7 and 8 say
which version of the code each run used.

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

**Tasks of sections 2 to 5** (SWE-bench Verified)

| Task | Repository | Bug |
|---|---|---|
| `sympy__sympy-13480` | sympy | typo `cotm` instead of `cothm` in `coth.eval` |
| `pydata__xarray-4629` | xarray | `merge(combine_attrs="override")` shares attrs with the first object |
| `sympy__sympy-14711` | sympy | `Vector + 0` raises `TypeError` |

Selection rationale: these are the three tasks the subject (section V.4)
recommends for initial testing, and all three belong to the moulinette's exam
pool (`EXAM_POOL`, 6 tasks, see section 8). Using the same three tasks for
every model keeps the comparison fair. They are not equally easy for our
agent: sympy-14711 takes 20 to 30 iterations, where the other two take 4 to 9
(except `ministral-3b-latest` on sympy-13480, 30 iterations), see section 2.

**Validation**: every solution file is checked with `moulinette_eval validate`
(correctness + metrics). Pass/Fail in this report is the moulinette result,
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

Pass count: codestral 2/3, ministral-14b 3/3, ministral-8b 3/3, ministral-3b
2/3, gemini-3.1-flash-lite 3/3 (13 of 15 runs). Every row was validated with
the moulinette on its own solution file. The backing files are
`bench/<model>__<task>.json`.

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

Two before/after comparisons of a change to the agent. 5.1 is measured on
existing traces. 5.2 is a re-run with the same task and the same model.

### 5.1 The `get_patch` fallback (measured on existing traces)

**Change**: when the loop ends without `final_answer`, the agent submits the
repository diff (`get_patch`) instead of an empty solution.

**Method**: the fallback only acts after the loop has ended, so removing it
changes nothing in a run that ends with `final_answer`. For a run that ends
without one, the solution becomes empty. We therefore took the existing
traces of section 2 and blanked the `solution` field, then validated the
result with the moulinette. We did not re-run the agent, so the comparison
uses identical traces.

| Run | With fallback | Without fallback |
|---|---|---|
| ministral-14b-latest, sympy-14711 | PASS | FAIL (validated with an empty solution) |
| ministral-3b-latest, sympy-13480 | PASS | FAIL (deduced, not validated) |

Over the 15 runs: 13 PASS with the fallback, 11 without. The other 13 runs
are unchanged: 11 end with `final_answer`, and 2 (codestral on sympy-14711,
ministral-3b on sympy-14711) fail either way.

Limit: this is a counterfactual on fixed traces. A real re-run could behave
differently because model output is not deterministic. This is why 5.2 re-runs
the agent.

### 5.2 The `search_code` rule in the prompt (re-run)

**Change**: remove from the SWE prompt (`agent_swebench/prompt.py`) the rule
saying that `file_pattern` of `search_code` is a file name pattern such as
`*.py`, never a path.

**Why this change**: before the rule existed, `ministral-8b-latest` failed
scikit-learn-13439 with an empty solution. It passed a path as `file_pattern`
12 times in that run, and each time got a false "no lines matched" (see 8.2).

**Protocol**: same task (scikit-learn-13439), same model
(`gemini-3.1-flash-lite`), same code and limits, 3 runs per condition, run one
after the other because of the Gemini rate limit. The only difference between
the two conditions is the rule. Measured on each solution file: moulinette
result, iterations, number of observations containing "no lines matched",
time.

| Condition | Run | Pass | Iterations | "no lines matched" | Time (s) |
|---|---|---|---|---|---|
| With the rule (current prompt) | 1 | PASS | 16 | 0 | 74 |
| With the rule (current prompt) | 2 | PASS | 21 | 0 | 57 |
| With the rule (current prompt) | 3 | PASS | 12 | 0 | 165 |
| Without the rule | 1 | PASS | 19 | 2 | 113 |
| Without the rule | 2 | PASS | 15 | 0 | 73 |
| Without the rule | 3 | PASS | 12 | 0 | 24 |

The backing files are `bench/ablation/gemini-3.1-flash-lite__scikit-learn-13439__<with|without>-rule-<n>.json`.

Result: with `gemini-3.1-flash-lite`, the rule makes no measurable
difference on this task. All 6 runs pass. The mean is 16.3 iterations with the
rule and 15.3 without, and 99 s with the rule and 70 s without; with 3 runs
per condition and iteration counts from 12 to 21 in both, these gaps are
within the spread between runs. The false "no lines matched" that motivated
the rule appears only in one run without it (2 observations), and we did not
check whether those two came from a path passed as `file_pattern`. The effect
seen with `ministral-8b-latest` (empty solution after 12 such answers) did
not show up with Gemini. The rule stays in the prompt, since it costs 4 lines
and targets a failure that weaker models do show.

## 6. Conclusions

**SWE-bench: selected model `gemini-3.1-flash-lite`.**
- 3/3 on the three benchmark tasks (section 2) and 6/6 on the exam pool with
  the code of 7 November (8.3), against 5/6 for `ministral-8b-latest` (8.2).
- The slowest task takes 156 s of the 900 s allowed, and no retry was recorded
  in section 3.
- Caveats: about 2.7 s per request against about 1 s for the Mistral models,
  about 15 requests per minute on the free tier (tasks must run one at a
  time), and two tasks that use many iterations (sympy-14711: 28 of 30,
  scikit-learn-13439: 20 of 30). All figures are single runs.

**Runner-up: `ministral-8b-latest`.** 3/3 on the benchmark tasks, with the
fewest iterations and tokens on sympy-14711 among the models that pass it
(20 iterations, 110,927 input tokens). It submits as soon as its tests pass
(0 extra iterations on all 3 tasks, section 4.2). It fails sympy-14711 in the
second pass of 8.2, and its sympy-14711 patch in section 2 is broader than the
issue asks.

**Other models**
- `ministral-14b-latest`: 3/3, but its sympy-14711 pass depends on the
  `get_patch` fallback: its tests only pass at step 30, the last iteration, so
  it had no step left to submit (sections 4.2 and 5.1).
- Disregarded: `mistral-large-4` (reasoning model, incompatible with the
  400-token reply cap), `mistral-small-latest` and `mistral-medium-latest` (no
  free quota on our key), `ministral-3b-latest` (loops on failed edits, 2/3,
  one invalid patch), `codestral-latest` (hits the input token cap on the
  hardest task).

**The `get_patch` fallback matters**: 13 runs pass with it, 11 without
(section 5.1). It rescues 2 of 15 runs (`ministral-14b-latest` on
sympy-14711, `ministral-3b-latest` on sympy-13480).

**The `search_code` prompt rule did not matter for Gemini**: scikit-learn-13439
passes 3 times out of 3 with it and 3 times out of 3 without it, in 12 to 21
iterations (section 5.2).

**MBPP: selected model `qwen/qwen3.8-27b` (Groq).** 15/15 on the three series
of 5 with the code of 7 November, and 37/40 on the two earlier series of 20,
all above the exam threshold of 4/5 (section 7). Of the 8 failures analysed in
the earlier runs, 4 come from hidden tests that contradict or are ambiguous
with the statement (137, 452, 461, 229), 2 from the model's behaviour (160,
260), and 2 were agent bugs that these runs revealed and that are fixed (286,
393).

**Docker cleanup**: no task container was left after the 6 runs of 8.3 or
after a `kill -9` of the agent (8.4).

**Limits of this report**: every cell is a single run with no variance
estimate, the SWE-bench model comparison covers three tasks (section 2) and
the models were not all run on the same version of the code (sections 2, 8.2
and 8.3).

## 7. MBPP check (moulinette `run-agent`)

**Method**: `scripts/eval_mbpp.sh N` draws N random tasks (`dump mbpp`, drawn
with replacement), runs the agent through `moulinette_eval run-agent 120` and
validates each solution. Model: `qwen/qwen3.8-27b` on Groq. Single runs, no
variance estimate, one model only (not the five of section 2). "Passed" is the
moulinette's overall result (correctness and metrics). The first three rows
were measured before the fixes of the audit; the other rows use the code of
the final branch at the time they were run.

| Run | Passed | Max agent time |
|---|---|---|
| Before merging the conversion feedback, 20 tasks | 18/20 | 52 s |
| After the merge, 5 tasks | 5/5 | 58 s |
| Branch code before the audit fixes, 10 tasks | 7/10 | 50 s |
| Final, 5 tasks that had failed before (137, 452, 461, 160, 260) | 0/5 | not recorded |
| Final, 20 tasks, first series | 19/20 | 97.4 s |
| Final, 20 tasks, second series | 18/20 | 42.1 s |
| Final, task 393 three times, after the fix | 3/3 | not recorded |
| Commit `3c7d559`, 5 tasks (237, 92, 393, 476, 465) | 5/5 | 43.0 s |
| Commit `3c7d559`, 5 tasks (425, 465, 97, 265, 284) | 5/5 | 30.4 s |
| Commit `3c7d559`, 5 tasks (88, 444, 446, 463, 389) | 5/5 | 22.0 s |

The exam threshold is 4/5 (80 %). The two earlier final series of 20 tasks
give 37/40 (92.5 %); their three failures are 286, 393 and 229. The three
series of 5 on `3c7d559` give 15/15. Of these, only the solution files of the
last series were kept; the first two were overwritten by the next series, and
their results are the moulinette outputs.

**Analysis of the failures** (correctness only, the metrics were valid)

Ambiguous tests (137, 452, 461, 229): the hidden test contradicts or is
ambiguous with the task statement, so the agent cannot guess it.
- 137: the test expects `zeros / (n - zeros)`, the statement says "ration of
  zeroes".
- 452: it expects `0` where the statement says "else return none".
- 461: the reference code returns inside the loop, so it only looks at the
  first character, and the model counts correctly.
- 229: the reference swaps elements, and the expected result depends on its
  algorithm.

Agent bugs found by these runs and fixed (286, 393):
- 286: the model wrote prose, then opened a code block that the token limit
  cut off. The reply was cut to 150 characters before the unclosed block was
  looked for, so the agent answered "no block" instead of "cut off". Fixed by
  checking the full reply first. Not measured again on 286.
- 393: the model submitted `max_length_list = lambda ...`, which was accepted
  as a final answer although it defines no function the tests could use.
  Fixed: a final answer must define a function or a lambda, and a refused
  answer is sent back to the model. 393 passes 3 times out of 3 after the fix,
  and once more in the series of 7 November.

Model failures (160, 260):
- 260: no solution. The model writes prose without any code block, the replies
  are cut by the 400-token cap and the run ends on `max_input_tokens`.
- 160: rerun on 7 November with the final code, FAIL, `success: false`, 5
  iterations. The model reaches code that passes the first public test and
  fails the second, `find_solution(1, 13, 17) == (4, 1)`: x + 13y = 17 has
  many integer solutions and the test expects one specific pair, which the
  model did not return. Two of its five replies used the full 400 tokens
  (steps 1 and 5). The cause was not investigated further.

## 8. Exam pool check (6 tasks)

The moulinette draws its SWE-bench exam tasks from a fixed pool of 6 tasks
(`EXAM_POOL`). Section 2 covers three of them. This section covers the whole
pool, with two models and two versions of the code. Single runs.

**8.1 Three more tasks, `ministral-8b-latest` (agent of 2 November, before
`agent/extract.py`)**

| Task | Pass | Iterations | Input tokens | Output tokens | Time (s) |
|---|---|---|---|---|---|
| django-11066 | PASS | 5 | 17,894 | 287 | 26.0 |
| sympy-18189 | PASS | 7 | 27,678 | 491 | 53.7 |
| scikit-learn-13439 | PASS | 11 | 45,858 | 592 | 31.8 |

With the three ministral-8b rows of section 2 (sympy-13480, xarray-4629,
sympy-14711), the model passed the 6 tasks of the pool with that agent. The
backing files are `bench/ministral-8b-latest__<task>.json`.

**8.2 Second pass, `ministral-8b-latest`, final agent and prompt of that
time (`run-agent 900`)**

| Task | Pass | Iterations |
|---|---|---|
| sympy-13480 | PASS | 4 |
| xarray-4629 | PASS | 5 |
| django-11066 | PASS | 7 |
| sympy-18189 | PASS | 7 |
| scikit-learn-13439 | PASS | 30 (limit reached) |
| sympy-14711 | FAIL | 30 |

5 of 6 pass, above the exam threshold of 2 of 3. The backing files are
`bench/final/ministral-8b-latest__<task>.json`.

Notes
- scikit-learn-13439 passes on its last allowed iteration: it is fragile.
  The same model and task took 11 iterations in 8.1, and failed with an
  empty solution before the prompt rule on `search_code` was added: the model
  passed a path as `file_pattern`, which gives a false "no lines matched"
  (12 times in that run).
- sympy-14711 fails because of the model's reasoning: it patches `Mul`
  instead of handling `other == 0`. No prompt rule was added for it, since a
  rule written for one task would overfit (V.1.2 of the subject).

**8.3 Pass with `gemini-3.1-flash-lite`, code of 7 November (commit
`3c7d559`)**

Run with `scripts/eval_swebench.sh` (moulinette `run-agent 900`, then
`validate`). "Time" is `total_time_seconds` of the solution file.

| Task | Pass | Iterations | Time (s) | Containers left |
|---|---|---|---|---|
| xarray-4629 | PASS | 7 | 18 | 0 |
| sympy-13480 | PASS | 8 | 21 | 0 |
| sympy-14711 | PASS | 28 | 156 | 0 |
| django-11066 | PASS | 6 | 28 | 0 |
| scikit-learn-13439 | PASS | 20 | 99 | 0 |
| sympy-18189 | PASS | 6 | 38 | 0 |

6 of 6 pass. The first pass over the 6 tasks took 486 s, validation and
container start included. The solution file of sympy-14711 from that pass
(27 iterations, 116 s, PASS) was deleted by the `kill -9` test of 8.4, which
restarts the same task, so sympy-14711 was run again alone with the same
script. The table shows that second run. The slowest task takes 156 s of the
900 s allowed. Two tasks use many of the 30 allowed iterations: sympy-14711
(28) and scikit-learn-13439 (20). The backing files are
`bench/final/gemini-3.1-flash-lite__<task>.json`.

The task container runs with `--network none`, and all 6 tasks pass, so their
eval scripts need no network.

8.2 and 8.3 are not strictly comparable: they ran on different commits, with
one run per cell. Gemini passing 6/6 against 5/6 for ministral-8b is an
indication, not a proof.

**8.4 Container cleanup**

- After each of the 6 runs of 8.3, `docker ps` showed no container of the
  task image.
- `kill -9` test: the script was started on sympy-14711, the agent was killed
  with `pkill -9 -f agent_swebench` 20 s after the task container appeared,
  and `docker ps -a` was run 8 s later. It listed no container of the task
  image, running or stopped. One trial.

## Reproducing

```
bash scripts/eval_mbpp.sh 5
bash scripts/eval_swebench.sh
```

`MODEL` and `URL` select the model and provider for both scripts, and
`MOUL_DIR` the moulinette folder if it is outside the repository. A single
SWE-bench run:

```
uv run python -m agent_swebench --task-file cache/swebench_task_<id>.json \
  --output bench/<model>__<task>.json --model-name <model> --provider-url <url>
```

The backing `solution.json` files are in `bench/`.
