*Benchmark data for Agent Smith, by speterse and jpik.*

# bench/

Backing `solution.json` files of `BENCHMARK_REPORT.md`, named
`<model>__<task>.json`, with a suffix for repeated runs and ablation
conditions. Each folder backs one part of the report.

| Folder | Report section | Contents |
|---|---|---|
| `final/` | 2.1, 3, 4, 9, 10 | Main comparison: 20 models on 7 SWE-bench tasks |
| `rerun/` | 2.1 | Re-runs of the 7 cells that hit Mistral's rate limit: the second attempt of the 5 that failed again (their first attempt is in `final/`), and both attempts of the 2 that passed (`__first-run` = first attempt) |
| `partial/` | 2.3 | Runs cut by a daily free quota, not counted in the comparison |
| `first_round/` | 1.1, 2.2, 4.3, 5.1, 8.1 | First round: 5 models on 3 tasks (2 November code), 3 more tasks for `ministral-8b-latest` (8.1), and the `mistral-large-4` HTTP 400 example |
| `repeated/swebench/` | 2.4 | 4 models, 7 tasks, 3 runs each (`__run<n>`), current code |
| `repeated/mbpp/` | 2.4 | 4 models on the 20 MBPP tasks of 5.3 |
| `exam_pool_nov6/` | 8.2 | `ministral-8b-latest` on the 6-task exam pool, 6 November code |
| `ablation/search_code_rule/` | 5.2 | `search_code` rule ablation: scikit-learn-13439, 3 runs with the rule and 3 without |
| `ablation/mbpp_prompt/` | 5.3 | MBPP prompt ablation: the same 20 tasks with the two-step and the one-step prompt |
| `ablation/hints/` | 5.4 | Task hints ablation: 4 tasks, 3 runs with `hints_text` and 3 without |
| `ablation/fewer_turns/` | 5.5 | Edit and test in one turn: `nemotron-3.5-super-120b` and `gemini-3.1-flash-lite`, 6 pool tasks, 3 runs each |
| `ablation/workflow_rules/` | 5.6 | Prompt rules (reproduce first, read whole functions), `nemotron-3.5-super-120b`, 6 pool tasks, 2 runs each |
| `ablation/edit_line_numbers/` | 5.6 | `edit_file` error with the line of each match, `nemotron-3.5-super-120b`, 6 pool tasks, 2 runs each |
| `ablation/stuck_note/` | 5.6 | Note after 8 turns without an edit, `nemotron-3.5-super-120b`, 6 pool tasks, 3 runs each |
| `ablation/reply_cap/` | 5.x | Reply cap raised from 400 to 1,000 tokens (SWE-bench), `nemotron-3.5-super-120b`, 6 pool tasks, 3 runs each |
| `ablation/keep_observations/` | 5.x | Last 3 observations kept in full in the history, on top of the reply cap, `nemotron-3.5-super-120b`, 6 pool tasks, 3 runs each |

The code version of each group of runs is in table 1.3 of the report.
Every run counted in the report was validated with `moulinette_eval validate`.
