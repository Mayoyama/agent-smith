*Benchmark data for Agent Smith, by speterse and jpik.*

# bench/

Backing `solution.json` files of `BENCHMARK_REPORT.md`, named
`<model>__<task>.json`. Each folder backs one part of the report.

| Folder | Report section | Contents |
|---|---|---|
| `final/` | 2.1, 3, 4, 9, 10 | Main comparison: 20 models on 7 SWE-bench tasks |
| `rerun/` | 2.1 | Both attempts of the cells re-run after a provider rate limit (`__first-run` = first attempt) |
| `partial/` | 2.3 | Runs cut by a daily free quota, not counted in the comparison |
| `first_round/` | 1.1, 2.2, 4.3, 5.1, 8.1 | First round: 5 models on 3 tasks (2 November code), plus the `mistral-large-4` HTTP 400 example |
| `exam_pool_nov6/` | 8.2 | `ministral-8b-latest` on the 6-task exam pool, 6 November code |
| `ablation/` | 5.2 | `search_code` rule ablation, 3 runs with and 3 without |

The code version of each group of runs is in table 1.3 of the report.
Every file was validated with `moulinette_eval validate`.
