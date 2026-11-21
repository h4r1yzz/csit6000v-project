# Fresh live confirmation on selected cases

### Table 1. New weekly plans

| Method | Feasible all-check pass | Passes per repeat, feasible | Explicit menu rejection on infeasible trials |
|---|---:|---|---:|
| Five specialists | 4/6 | 1/2, 1/2, 2/2 | 3/3 |
| One call | 0/6 | 0/2, 0/2, 0/2 | 0/3 |
| Generalist + revision | 0/6 | 0/2, 0/2, 0/2 | 0/3 |

### Table 2. Replanning after a profile change

| Method | Feasible all-check pass | Passes per repeat, feasible | Explicit menu rejection on infeasible trials | Successful repair when prior fails new rules |
|---|---:|---|---:|---:|
| Five specialists | 6/6 | 2/2, 2/2, 2/2 | 3/3 | 6/6 |
| One call | 0/6 | 0/2, 0/2, 0/2 | 0/3 | 0/6 |
| Generalist + revision | 0/6 | 0/2, 0/2, 0/2 | 0/3 | 0/6 |

### Table 3. Cost and elapsed time per attempted scenario

| Suite | Method | Trials | Time in seconds, median [IQR] | Mean model calls | Total tokens per trial, median [IQR] | Complete usage |
|---|---|---:|---:|---:|---:|---:|
| Planning | Five specialists | 9 | 45.9 [37.1–51.9] | 3.56 | 6,243 [4,314–13,246] | 9/9 |
| Planning | One call | 9 | 22.6 [19.0–24.7] | 1.00 | 3,446 [3,305–3,566] | 9/9 |
| Planning | Generalist + revision | 9 | 32.9 [20.3–39.4] | 1.67 | 7,355 [3,595–7,514] | 9/9 |
| Adaptation | Five specialists | 9 | 60.3 [41.1–63.2] | 4.00 | 15,914 [5,188–16,134] | 9/9 |
| Adaptation | One call | 9 | 21.3 [19.5–26.8] | 1.00 | 4,173 [4,044–4,264] | 9/9 |
| Adaptation | Generalist + revision | 9 | 33.8 [25.1–38.1] | 1.67 | 8,978 [4,274–9,383] | 9/9 |

### Table 4. Outcomes across all scheduled trials

| Suite | Method | Valid draft | Invalid draft | Explicit menu conflict | Execution/output error | Transport error |
|---|---|---:|---:|---:|---:|---:|
| Planning | Five specialists | 4 | 0 | 3 | 2 | 0 |
| Planning | One call | 0 | 0 | 9 | 0 | 0 |
| Planning | Generalist + revision | 0 | 0 | 9 | 0 | 0 |
| Adaptation | Five specialists | 6 | 0 | 3 | 0 | 0 |
| Adaptation | One call | 0 | 0 | 9 | 0 | 0 |
| Adaptation | Generalist + revision | 0 | 0 | 9 | 0 | 0 |

### Table 5. Specialist workflow flow checks

| Suite | Feasible cases completing all five stages | Infeasible cases correctly stopped at nutrition | Other early stage failures |
|---|---:|---:|---:|
| Planning | 4/6 | 3/3 | 2 |
| Adaptation | 6/6 | 3/3 | 0 |
