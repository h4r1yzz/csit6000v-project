# FitPilot

FitPilot is a fitness planning app built for CSIT6000V. Its React dashboard tracks exercise pose in the browser. The FastAPI backend coordinates five planning and feedback agents and stores profiles, plans, and progress in PostgreSQL. Live agent requests use TACC Qwen or a compatible model endpoint.

[Final grading package](https://github.com/h4r1yzz/csit6000v-project/tree/grading-final) · [Public GitHub repository](https://github.com/h4r1yzz/csit6000v-project)

The full live evaluation uses the [pinned v4 source commit](https://github.com/h4r1yzz/csit6000v-project/tree/ca94084617e3458ce639b7074debfe9029af3eb9), `ca94084617e3458ce639b7074debfe9029af3eb9`. The final package includes that application and evaluator with setup materials and the [full run evidence](evaluation/full-v4).

## Getting Started Instructions

### Prerequisites

- Git, Python 3.11, Node.js 22.18 or later with npm, and a macOS or Linux shell.
- A disposable PostgreSQL database and a login that can create schemas in it. Use a local or hosted database, or Docker with Compose.
- Internet access for dependency installation. The smoke test runs without a camera, GPU, TACC account, or model endpoint.

### Install and configure

```bash
git clone --branch grading-final \
  https://github.com/h4r1yzz/csit6000v-project.git
cd csit6000v-project
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
```

### Configure PostgreSQL

For an existing PostgreSQL database, export its disposable connection string as `TEST_DATABASE_URL` in the same shell. To create a database on a running local server, use the following commands.

```bash
createdb fitpilot_artifact
export TEST_DATABASE_URL='postgresql:///fitpilot_artifact'
```

For a local Docker database, [Compose](compose.yaml) starts PostgreSQL 17.12 on port `54327`. The credentials below are for this local database. `docker compose down` stops the service and preserves the named volume.

```bash
docker compose up -d --wait postgres
export TEST_DATABASE_URL='postgresql://fitpilot:fitpilot_dev@127.0.0.1:54327/fitpilot_artifact'
```

### Run the end-to-end smoke test

```bash
backend/.venv/bin/python scripts/smoke.py
```

The test registers an account, calls all five stages using simulated model responses, validates the draft, approves it, and reads back the active plan. It creates and removes isolated PostgreSQL schemas. A passing run prints the following lines.

```text
PASS: account -> five simulated model stages -> valid draft -> approval -> persisted active plan
SIMULATED MODEL: this checks application integration, not live inference or recommendation quality.
```

### Open the app

```bash
DATABASE_URL="$TEST_DATABASE_URL" python3.11 scripts/dev.py
```

Open the [dashboard](http://127.0.0.1:5173) or [API documentation](http://127.0.0.1:8000/docs). Create an app account to open the dashboard. Stop the launcher with Ctrl+C. See [the example environment file](backend/.env.example) for available settings and the [TACC setup guide](backend/tacc/README.md) for live planning, specialist agents, and chat.

## Detailed Instructions

### Verify the application

With `TEST_DATABASE_URL` still exported, run the full local check. It builds the frontend, runs the backend and pose tests, and runs the API smoke test. Each check should print `PASS`. The fresh v4 checkout passed 43 backend tests and 17 synthetic pose tests on Python 3.11.18 and PostgreSQL 17.12. See the [verification and launch logs](evaluation/full-v4).

```bash
RUN_DIR=$(mktemp -d)
backend/.venv/bin/python scripts/verify.py --output "$RUN_DIR/verification.json"
```

### Test cases and scoring

| Suite | Data | Metric |
| --- | --- | --- |
| Planning | [20 synthetic profiles](evaluation/planning_cases.json), including two infeasible menus | Valid draft rate on feasible trials and explicit rejection rate on infeasible trials |
| Adaptation | [10 profile changes](evaluation/adaptation_cases.json) with validated prior plans, including two infeasible changes | Valid replan rate and repair rate when the prior plan breaks the new constraints |
| Feedback | A missing session and two synthetic pose summaries in [the feedback runner](scripts/evaluate_feedback.py) | Returned metric consistency and a confidence note when measurements are absent or low confidence |

The live comparison uses the same case inputs and final validator for the five specialists, a one-call generalist, and a generalist with one revision. The validator checks schedule, session time, exercise eligibility, dietary compatibility, catalog facts, weekly servings, and budget. The traces include model responses, specialist stage order and status, validation, latency, calls, and tokens. See the [scoring methodology](docs/EVALUATION.md).

### Sample workflows and chat history

The [reviewer walkthrough](docs/EVALUATION-EXAMPLES.md) links test cases to live response excerpts, shows both successful and failed agent flows, and explains what the app stores. Run the two-turn chat demo with the same disposable PostgreSQL database. It simulates model replies and verifies that all four messages reload after login and all three model requests are recorded.

```bash
backend/.venv/bin/python scripts/demo_chat.py
```

### Rebuild tables from the recorded runs

This command reads the fresh full run and prints Tables 1–5 using only Python. Compare the output with the [fresh tables](evaluation/full-v4/tables.md) and the [original tables](evaluation/results/tables.md).

```bash
python3.11 scripts/summarize_evaluation.py \
  --planning evaluation/full-v4/planning.json \
  --adaptation evaluation/full-v4/adaptation.json
```

### Rerun the live evaluation

Start the course Qwen service and connect through the [TACC setup guide](backend/tacc/README.md). With the tunnel active, run the commands below from the repository root in a second shell with `TEST_DATABASE_URL` exported. The live smoke test checks all five stages, approval, and readback before the benchmark. Replace the example URL if you use a different reachable address.

```bash
unset LLM_BASE_URL LLM_MODEL LLM_API_KEY LLM_TIMEOUT_SECONDS
export QWEN_BASE_URL='http://127.0.0.1:18000/v1'
export QWEN_MODEL='qwen3.8-27b'
export QWEN_TIMEOUT_SECONDS=90
backend/.venv/bin/python scripts/smoke.py --live
RUN_DIR=$(mktemp -d)
backend/.venv/bin/python scripts/evaluate.py --suite planning \
  --repeats 3 --workers 4 --output "$RUN_DIR/planning.json"
backend/.venv/bin/python scripts/evaluate.py --suite adaptation \
  --repeats 3 --workers 4 --output "$RUN_DIR/adaptation.json"
backend/.venv/bin/python scripts/evaluate_feedback.py --output "$RUN_DIR/feedback.json"
backend/.venv/bin/python scripts/summarize_evaluation.py \
  --planning "$RUN_DIR/planning.json" --adaptation "$RUN_DIR/adaptation.json" \
  --output "$RUN_DIR/tables.md"
```

The full run produces 180 planning trials and 90 adaptation trials with three repeats per case and method. The runner uses UTC, a temperature of 0.2, and four concurrent workers in the commands above. Allow for GPU scheduling and the course job's one-hour limit. If the job expires, stop the run, reconnect to a new service and add `--resume` to the interrupted command with the same arguments and output path. Use a new output directory for a complete rerun if the checkpoint contains outage failures.

The [reproducibility guide](docs/REPRODUCIBILITY.md) links the exact source commit, a clean installation check, the replay of the original 270 trials, and the fresh full live evaluation.

### Results and report references

Use the [fresh Tables 1–5](evaluation/full-v4/tables.md) and [original report tables](docs/EVALUATION.md#recorded-live-results) to locate each result. The [full run evidence](evaluation/full-v4) includes all 270 trial traces and the [side-by-side scores](evaluation/full-v4/comparison.md).

| Reference | Original run | Fresh clean v4 run |
| --- | --- | --- |
| Table 1 · Planning | Specialists 52/54. One call 0/54. Revision 0/54. Specialists rejected 6/6 infeasible trials. | Specialists 53/54. One call 0/54. Revision 0/54. Specialists rejected 6/6 infeasible trials. |
| Table 2 · Adaptation | Specialists 24/24. One call 1/24. Revision 3/24. Specialists rejected 6/6 infeasible trials. | Specialists 22/24. One call 1/24. Revision 4/24. Specialists rejected 6/6 infeasible trials. |
| Tables 3 and 4 · Cost and outcomes | Planning median 75.3 s for specialists, 27.8 s for one call, and 46.8 s for revision. | Planning median 64.2 s for specialists, 27.3 s for one call, and 51.1 s for revision. See the fresh tables for spread, tokens, and failure counts. |
| Table 5 · Stage flow | All five stages completed in 52/54 feasible planning and 24/24 feasible adaptation trials. | All five stages completed in 53/54 feasible planning and 22/24 feasible adaptation trials. |

The [fresh feedback API record](evaluation/full-v4/feedback.json) passed 3/3 synthetic summary cases.

### Limitations and expected variation

- The live results apply to these synthetic cases, prompts, catalog, validators, and course Qwen configuration. The specialist workflow also uses catalog logic and structured stages, so the comparison cannot isolate the effect of agent count.
- Treat the recorded rates as reference points. Compare feasible pass rates, explicit rejections, and stage completion. Model outputs and token use vary with sampling. Network and GPU load affect latency. The report includes per-repeat counts and latency spread.
- Live reruns require authorized access to the course model or a reachable substitute. A different model can change the results. The local smoke test and recorded tables can be checked independently of that access.
- The pose tests use synthetic landmarks and the feedback API uses synthetic summaries. Real-video pose accuracy and rep-count error remain unmeasured. See the [pose protocol](docs/POSE.md) for a labeled-video assessment.

See the [implementation guide](docs/IMPLEMENTATION.md), [API reference](docs/API.md) and [database guide](docs/DATABASE.md) for system details. This README follows the [NSDI ’27 artifact instructions](https://www.usenix.org/conference/nsdi27/call-for-artifacts).
