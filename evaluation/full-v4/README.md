# Full live evaluation on clean FitPilot v4

**Evaluated source** [`ca94084617e3458ce639b7074debfe9029af3eb9`](https://github.com/h4r1yzz/csit6000v-project/tree/ca94084617e3458ce639b7074debfe9029af3eb9), tagged `grading-submission-2026-11-21-v4`. The run used a fresh clone of the public GitHub repository. All outputs were written outside the clone. The checkout was clean before and after the live commands.

## How to inspect and rerun

- [Run manifest](live-run.json) records the source SHA, model, configuration, commands, TACC allocations, exit codes, and UTC timestamps. [Source and tool versions](source.txt) includes the runner and case-bank hashes. [Python dependencies](python-environment.txt) lists the installed versions.
- [Planning JSON](planning.json) and [adaptation JSON](adaptation.json) contain the full per-trial request and response traces, validation decisions, usage, and specialist stage order. [Planning log](planning.log) and [adaptation log](adaptation.log) record trial completion.
- [Fresh Tables 1–5](tables.md) were regenerated from the new traces. [Comparison](comparison.md) shows original and fresh scores using the same case-bank denominators and validator.
- [Feedback JSON](feedback.json) and [feedback log](feedback.log) cover absent, low-confidence, and clear synthetic summaries. [Live smoke log](live-smoke.log) covers all five live stages, plan approval, and PostgreSQL readback.
- [Installation verification](verification.json) records the frontend production build, 43 backend tests, 17 synthetic pose tests, and simulated smoke check. [App launch log](app-launch.log) verifies the dashboard and API with a connected native PostgreSQL database. The [Compose log](compose-config.log) covers manifest validation with the Compose CLI.

Follow the [grading reproducibility guide](../../docs/REPRODUCIBILITY.md) to check the exact Git revision, rerun the live commands, or regenerate the published tables without model access.

## Scope

The fresh run covers 20 planning profiles and 10 adaptation scenarios, each three times with all three methods. It uses four workers and the course `qwen3.8-27b` service. Both runs are system comparisons on synthetic data. The specialist pipeline also includes catalog filtering and validation, so scores measure the configured workflows. The pose API checks use synthetic summaries. Deployment on TACC requires authorized access, and model results and latency can vary between runs.

## Observed results

- **Planning.** Specialists 53/54. One call 0/54. Revision 0/54. Specialists rejected 6/6 infeasible trials. Planning median 64.2 s for specialists, 27.3 s for one call, and 51.1 s for revision.
- **Adaptation.** Specialists 22/24. One call 1/24. Revision 4/24. Specialists rejected 6/6 infeasible trials.
- **Specialist stage flow.** All five stages completed in 53/54 feasible planning and 22/24 feasible adaptation trials.
- **Feedback API.** 3/3 synthetic summary checks passed.

The original and fresh measurements support the same system-level finding. The configured specialist workflow finishes more feasible drafts than either generalist baseline on this case bank. The specialist workflow also uses more model calls and has higher median planning latency. Compare the full tables for the outcome counts and latency spread.

The feasible planning misses are P04 (repeat 1). The raw trace and Table 4 retain every failed attempt.

The adaptation run resumed at 67 completed trials after the first allocation approached its time limit. The scheduler status query later timed out after the completed 90-trial checkpoint had been saved. A subsequent `--resume` verified it with zero new trials. The A03 session-time failure and A08 transport failure remain in the adaptation results.
