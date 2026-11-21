### Table 1. New weekly plans

| Method | Feasible all-check pass | Passes per repeat, feasible | Explicit menu rejection on infeasible trials |
|---|---:|---|---:|
| Five specialists | 53/54 | 17/18, 18/18, 18/18 | 6/6 |
| One call | 0/54 | 0/18, 0/18, 0/18 | 3/6 |
| Generalist + revision | 0/54 | 0/18, 0/18, 0/18 | 3/6 |

### Table 2. Replanning after a profile change

| Method | Feasible all-check pass | Passes per repeat, feasible | Explicit menu rejection on infeasible trials | Successful repair when prior fails new rules |
|---|---:|---|---:|---:|
| Five specialists | 22/24 | 8/8, 8/8, 6/8 | 6/6 | 14/15 |
| One call | 1/24 | 0/8, 1/8, 0/8 | 3/6 | 0/15 |
| Generalist + revision | 4/24 | 1/8, 1/8, 2/8 | 3/6 | 1/15 |

### Table 3. Cost and elapsed time per attempted scenario

| Suite | Method | Trials | Time in seconds, median [IQR] | Mean model calls | Total tokens per trial, median [IQR] | Complete usage |
|---|---|---:|---:|---:|---:|---:|
| Planning | Five specialists | 60 | 64.2 [56.7–70.2] | 4.70 | 14,474 [13,704–14,970] | 60/60 |
| Planning | One call | 60 | 27.3 [23.5–30.4] | 1.00 | 3,562 [3,386–3,640] | 60/60 |
| Planning | Generalist + revision | 60 | 51.1 [44.3–58.4] | 1.90 | 8,362 [7,737–8,718] | 60/60 |
| Adaptation | Five specialists | 30 | 71.3 [57.5–76.0] | 4.37 | 16,860 [15,804–17,532] | 29/30 |
| Adaptation | One call | 30 | 24.7 [22.6–27.2] | 1.00 | 4,239 [4,135–4,286] | 30/30 |
| Adaptation | Generalist + revision | 30 | 47.3 [36.5–56.2] | 1.80 | 9,640 [8,938–9,870] | 30/30 |

### Table 4. Outcomes across all scheduled trials

| Suite | Method | Valid draft | Invalid draft | Explicit menu conflict | Execution/output error | Transport error |
|---|---|---:|---:|---:|---:|---:|
| Planning | Five specialists | 53 | 0 | 6 | 1 | 0 |
| Planning | One call | 0 | 0 | 60 | 0 | 0 |
| Planning | Generalist + revision | 0 | 4 | 56 | 0 | 0 |
| Adaptation | Five specialists | 22 | 0 | 6 | 1 | 1 |
| Adaptation | One call | 1 | 1 | 28 | 0 | 0 |
| Adaptation | Generalist + revision | 4 | 4 | 22 | 0 | 0 |

### Table 5. Specialist workflow flow checks

| Suite | Feasible cases completing all five stages | Infeasible cases correctly stopped at nutrition | Other early stage failures |
|---|---:|---:|---:|
| Planning | 53/54 | 6/6 | 1 |
| Adaptation | 22/24 | 6/6 | 2 |
