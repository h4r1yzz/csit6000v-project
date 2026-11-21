# Live planning and adaptation evaluation

FitPilot's central claim is that its coordinator can produce an approvable weekly workout and meal draft under explicit constraints. We measure completed drafts against a fixed rule set and measure the inference cost of producing them. Any between-method difference applies to the complete configurations described below.

The [reviewer walkthrough](EVALUATION-EXAMPLES.md) shows individual inputs, live outputs, a revision failure, examples of prose that the metrics miss, and a replayable chat persistence demo. The [fresh full run](../evaluation/full-v4) repeats all 270 live trials from the clean v4 source commit and compares its tables with the original recordings below.

## Cases and comparisons

The planning suite includes 18 feasible synthetic profiles and two infeasible profiles. P19 has a zero meal budget. P20 requests halal meals, which the current catalog cannot certify. P01 and P07 resolve to the same equipment profile. These are scenario trials, and the case bank does not represent 20 independent people.

Each of the ten adaptation scenarios starts with the same synthetic prior plan for its initial profile, constructed from seeded catalog entries using the application's deterministic planning helpers. The runner validates that prior before changing the profile. All methods receive that same prior. Eight changed profiles are feasible and two introduce the same catalog infeasibilities used in planning. Some changes leave the prior valid, for example relaxing the budget. We separately score feasible changes that actually invalidate the prior. This experiment measures the ability to propose a valid plan following a change. It does not score whether a user should have replanned or how many exercises a user would prefer to keep.

Every scoring decision uses the same seven application checks:

1. Exactly the requested number of distinct sessions on the selected days.
2. Session duration at or below the requested limit and enough time for the prescribed work, rests and warm-up.
3. Only catalog exercises that pass the app's equipment, experience and recorded limitation filters.
4. Only meals compatible with the supported diet and allergy filters.
5. Catalog-matching ingredients, calories, protein and per-serving prices.
6. Exactly 21 meal servings per week.
7. A correctly calculated total in the profile's currency within the weekly budget.

These rules test consistency with the sample catalog and supported preference filters. They do not measure clinical safety, real grocery prices, coach quality or long-term fitness outcomes.

| Method | Generation policy |
|---|---|
| Five specialists | FitPilot's production workflow with specialized prompts, shared state, deterministic day assignment, catalog menu selection, per-stage schemas and targeted validation revisions. A failed stage can end the workflow early. |
| One call | A generalist receives the complete user context, catalogs, selected weekdays, eligible exercises, compatible meal facts, time and nutrition rules, and the complete plan schema. It has one attempt at the entire plan. |
| Generalist + revision | The same initial request as one call. If the first draft fails a check, the model gets one revision with the validation feedback. |

The experiment compares deployable pipelines. Modular specialization, prompt design, catalog construction, validation and retry policies all differ. The comparison cannot isolate the effect of agent count alone. All modes use the same model service, case inputs and final validator. They request JSON at temperature 0.2 with no fixed generation seed. The baselines have a 4,000-output-token ceiling per request and the specialist flow uses its deployment limits.

The trace records every model request and raw response. For the specialist pipeline it also records each normalized stage output, source, status, per-stage call count and order. A feasible workflow is expected to run goal planning → exercise planning → nutrition → exercise feedback → evaluation/adaptation. An infeasible menu is expected to stop at nutrition after the earlier stages complete; this is scored as correct rejection rather than a complete five-stage workflow. Generalist drafts that abstain on feasible profiles receive validator feedback and their one allowed revision. Transport failures and malformed responses are retained as failures.

## Scoring

For feasible scenarios, success requires all seven checks to pass. A transport error, malformed output or invalid draft counts as a miss. For infeasible scenarios, success requires an explicit menu conflict. The specialist workflow can surface its deterministic “no menu meets the recorded dietary and budget constraints” error. The baselines can explicitly signal an unaffordable or incompatible menu with empty meals and the correct reason in their summary. An arbitrary invalid draft receives zero credit. This metric tests recognition of a menu conflict; the specialist message does not distinguish which of the two constraints failed. Provider failures never receive rejection credit.

Each method runs on each case three times in a fixed shuffled dispatch order. Tables 1 and 2 report counts over repeats and the feasible pass count for each repeat. Replicates on the same synthetic case are repeated measures, not independent user samples. Table 2 also breaks out the trials in which repair was necessary. Table 3 measures elapsed wall time from the start of each dispatched scenario through validation, excluding TACC allocation, model loading, PostgreSQL setup and waiting in the evaluator's process pool. Service contention from concurrently submitted requests is included. Time and token entries give the median and interquartile range; mean calls count every attempted transport request including failures. Token statistics use only trials with complete provider usage and state coverage. Table 4 distinguishes validation misses from pipeline and transport failures. Table 5 summarizes the observed specialist stage order and completion. Planning method runs may be checkpointed separately and merged with `scripts/merge_evaluation.py`; per-method runner hashes are retained in the combined JSON.

## Recorded live results

The recorded runs used TACC Qwen `qwen3.8-27b` through the local SSH tunnel on 2026-11-21. The service jobs ran vLLM 0.26.0 with the course Qwen 3.8-27B AWQ model on two GPUs. All planning and adaptation cases were run three times per method. Full requests, model responses, usage, timing, checks and stage outputs are in `evaluation/results/planning.json`, `planning-multi-agent-flow.json`, `planning-generalist-revision.json`, `planning-single-call.json` and `adaptation.json`. `planning.json` stores the runner hash for each method because the method runs were checkpointed separately; the one-call method's behavior was unchanged when the specialist trace and corrected revision handling were added.

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

The specialist workflow completed the five stages in order on every feasible scenario counted as a complete flow. The six infeasible trials in each suite stopped at nutrition, as expected. The two planning execution/output errors stopped early and remain counted as failures. The one-call and generalist baselines received the same user constraints, eligible exercise list, compatible meal facts and final validator, but still frequently abstained on feasible cases. This is evidence about these specific prompts and model configuration, not a general claim that every multi-agent design outperforms every single-agent baseline.

The signed-in exercise-feedback endpoint also passed 3/3 live checks in `evaluation/results/feedback.json`: no session, low-confidence synthetic measurements, and a clear synthetic summary. The endpoint returned the supplied metrics and appropriate confidence notes. These inputs were manually constructed summaries; the model did not analyze video frames. No labeled workout clips were provided, so real-video pose accuracy and rep-count error were not measured.

## Reproduce

From the repository root, set TEST_DATABASE_URL to a disposable PostgreSQL database on which the role can create schemas. Configure the Qwen service and tunnel as described in the TACC guide and export QWEN_BASE_URL or pass a private environment file. Use the worker count and model recorded in the result JSON when reproducing latency. Set FITPILOT_TIMEZONE=UTC for the evaluation; the runner enforces UTC within its isolated database scope. The runner writes synthetic request traces, returned outputs, seven check results when available, per-request error and usage, and wall time. Its temporary schema is dropped when the command exits normally.

Each suite accepts a new output filename and --resume to continue a matching checkpoint. Inspect both raw files then run scripts/summarize_evaluation.py to regenerate the metric tables. Graders can compare feasibility rates and outcome counts first, then inspect representative failed cases. Individual Qwen responses, failure patterns and timing may change between runs. The three repeats describe within-run variation; the measured numbers are not fixed correctness thresholds.
