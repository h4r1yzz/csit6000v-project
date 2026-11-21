### Table 1. New weekly plans

| Method | Feasible all-check pass | Passes per repeat, feasible | Explicit menu rejection on infeasible trials |
|---|---:|---|---:|
| Five specialists | 52/54 | 18/18, 16/18, 18/18 | 6/6 |
| One call | 0/54 | 0/18, 0/18, 0/18 | 3/6 |
| Generalist + revision | 0/54 | 0/18, 0/18, 0/18 | 3/6 |

### Table 2. Replanning after a profile change

| Method | Feasible all-check pass | Passes per repeat, feasible | Explicit menu rejection on infeasible trials | Successful repair when prior fails new rules |
|---|---:|---|---:|---:|
| Five specialists | 24/24 | 8/8, 8/8, 8/8 | 6/6 | 15/15 |
| One call | 1/24 | 1/8, 0/8, 0/8 | 3/6 | 1/15 |
| Generalist + revision | 3/24 | 2/8, 1/8, 0/8 | 3/6 | 1/15 |

### Table 3. Cost and elapsed time per attempted scenario

| Suite | Method | Trials | Time in seconds, median [IQR] | Mean model calls | Total tokens per trial, median [IQR] | Complete usage |
|---|---|---:|---:|---:|---:|---:|
| Planning | Five specialists | 60 | 75.3 [67.8–79.9] | 4.65 | 14,596 [13,647–14,923] | 60/60 |
| Planning | One call | 60 | 27.8 [23.9–31.3] | 1.00 | 3,548 [3,399–3,643] | 60/60 |
| Planning | Generalist + revision | 60 | 46.8 [38.2–51.1] | 1.90 | 8,431 [7,884–8,704] | 60/60 |
| Adaptation | Five specialists | 30 | 67.8 [53.4–72.1] | 4.43 | 16,716 [15,624–17,641] | 30/30 |
| Adaptation | One call | 30 | 23.7 [20.9–26.8] | 1.00 | 4,242 [4,167–4,277] | 30/30 |
| Adaptation | Generalist + revision | 30 | 46.9 [36.5–52.9] | 1.77 | 9,550 [8,671–9,702] | 30/30 |

### Table 4. Outcomes across all scheduled trials

| Suite | Method | Valid draft | Invalid draft | Explicit menu conflict | Execution/output error | Transport error |
|---|---|---:|---:|---:|---:|---:|
| Planning | Five specialists | 52 | 0 | 6 | 2 | 0 |
| Planning | One call | 0 | 0 | 60 | 0 | 0 |
| Planning | Generalist + revision | 0 | 4 | 56 | 0 | 0 |
| Adaptation | Five specialists | 24 | 0 | 6 | 0 | 0 |
| Adaptation | One call | 1 | 0 | 29 | 0 | 0 |
| Adaptation | Generalist + revision | 3 | 2 | 25 | 0 | 0 |

### Table 5. Specialist workflow flow checks

| Suite | Feasible cases completing all five stages | Infeasible cases correctly stopped at nutrition | Other early stage failures |
|---|---:|---:|---:|
| Planning | 52/54 | 6/6 | 2 |
| Adaptation | 24/24 | 6/6 | 0 |
