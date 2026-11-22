# FitPilot

FitPilot studies how to produce personalized workout and meal plans that satisfy scheduling, equipment, dietary, and budget constraints together. Its central contribution is a bounded five-agent planning workflow that shares user context, builds from curated exercise and meal catalogs, and validates the draft before the user can approve it. We compare this workflow with one-call and revision-based generalists over 270 live TACC Qwen trials, measuring constraint satisfaction, completion, latency, and model usage. Browser pose tracking supplies optional measurements to the exercise feedback stage.

[Grading repository (`grading-final`)](https://github.com/h4r1yzz/csit6000v-project/tree/grading-final)

The grading repository contains the app, evaluator, and [full run evidence](evaluation/full-v4). The clean live trials used [source commit `ca940846`](https://github.com/h4r1yzz/csit6000v-project/tree/ca94084617e3458ce639b7074debfe9029af3eb9). The grading checkout includes later dashboard changes and the same model workflow, case inputs, and scoring scripts.

## Getting Started Instructions

### Prerequisites

- Git, Python 3.11, Node.js 22.18 or later with npm, and a macOS or Linux shell.
- A PostgreSQL login that can create schemas. Choose Neon, a local PostgreSQL installation, or Docker below. Use a disposable database or Neon branch for verification.
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

Choose one option. The app reads `DATABASE_URL` from the private `backend/.env` file. Create that file from the example if it is missing. Edit the database lines for your chosen option and keep any existing model settings.

```bash
test -f backend/.env || cp backend/.env.example backend/.env
```

### Option 1. Neon (hosted PostgreSQL)

In your Neon project's **Connect** dialog, select your branch, database, and role. Copy the pooled and direct connection strings for that same database into `backend/.env`. Use a disposable branch if you plan to run verification. [Neon connection instructions](https://neon.com/docs/connect/connect-from-any-app)

```dotenv
DATABASE_URL='PASTE_POOLED_NEON_URL_HERE'
DATABASE_URL_UNPOOLED='PASTE_DIRECT_NEON_URL_HERE'
```

Replace both placeholders with your full URLs, including their SSL parameters. Keep the quotes and keep the file private. Neon hosts the database, so proceed to the smoke test without starting a local server.

### Option 2. Install PostgreSQL locally

On macOS with Homebrew, install and start PostgreSQL 17. [Homebrew PostgreSQL 17](https://formulae.brew.sh/formula/postgresql@17)

```bash
brew install postgresql@17
export PATH="$(brew --prefix postgresql@17)/bin:$PATH"
brew services run postgresql@17
pg_isready
```

Once `pg_isready` reports `accepting connections`, create the database once.

```bash
createdb fitpilot_artifact
```

Set `DATABASE_URL='postgresql:///fitpilot_artifact'` and `DATABASE_URL_UNPOOLED=` in `backend/.env`. If the database already exists, skip `createdb`. On Linux, use your distribution's PostgreSQL server and client packages and a role with schema creation permission, or use Option 3. [PostgreSQL downloads](https://www.postgresql.org/download/)

### Option 3. Docker

Install Docker with Compose v2 and start the Docker engine. From the repository root, use [Compose](compose.yaml) to start PostgreSQL 17.12. It creates `fitpilot_artifact` and waits for the health check.

```bash
docker compose version
docker compose up -d --wait postgres
```

Use these local-only settings in `backend/.env`.

```dotenv
DATABASE_URL='postgresql://fitpilot:fitpilot_dev@127.0.0.1:54327/fitpilot_artifact'
DATABASE_URL_UNPOOLED=
```

### Run the end-to-end smoke test

Set `TEST_DATABASE_URL` in your shell. Use the direct URL of a disposable Neon branch for Option 1 or the local database URL shown for Option 2 or 3. The verification scripts read shell variables. Clear any inherited direct app URL so verification creates and cleans up its test schemas on the selected test database.

```bash
export TEST_DATABASE_URL='PASTE_DISPOSABLE_DATABASE_URL_HERE'
unset DATABASE_URL_UNPOOLED
backend/.venv/bin/python scripts/smoke.py
```

The test registers an account, calls all five stages using simulated model responses, validates the draft, approves it, and reads back the active plan. It creates and removes isolated PostgreSQL schemas. A passing run prints the following lines.

```text
PASS: account -> five simulated model stages -> valid draft -> approval -> persisted active plan
SIMULATED MODEL: this checks application integration, not live inference or recommendation quality.
```

### Open the app

```bash
env -u DATABASE_URL -u DATABASE_URL_UNPOOLED python3.11 scripts/dev.py
```

Open the [dashboard](http://127.0.0.1:5173) or [API documentation](http://127.0.0.1:8000/docs). Create an app account to open the dashboard. Stop the launcher with Ctrl+C. See [the example environment file](backend/.env.example) for available settings and the [TACC setup guide](backend/tacc/README.md) for live planning, specialist agents, and chat.

Check the local API with `curl -fsS http://127.0.0.1:8000/api/health`. The response should include `status: ok` and `database: connected`.

After stopping the app, use `brew services stop postgresql@17` for the Homebrew service or `docker compose down` for Docker. The database data persists.

### Walk through a live planning case

With Qwen connected on the `grading-final` checkout, create an account and open **Preferences**. Choose two days per week, Tuesday and Saturday, 35 minutes per session, bodyweight and dumbbells, and a USD 70 food budget. Use the starting goal, beginner experience, and high-protein preference. Select **Save & continue**, then **Build my week**.

Inspect Tuesday and Saturday sessions and 21 meal servings. Open **Preference checks** to verify seven passing checks, then select **Approve my week** and reload to confirm the plan persists. The [recorded P02 trial](evaluation/full-v4/planning.json) produced two 35-minute sessions and an estimated menu cost of USD 67.90 in repeat 1. Reruns can select different valid exercises and meals.

## Detailed Instructions

### Verify the application

With `TEST_DATABASE_URL` still exported, run the full local check. It builds the frontend, runs the backend and pose tests, and runs the API smoke test. Each check should print `PASS`. The fresh v4 checkout passed 43 backend tests and 17 synthetic pose tests on Python 3.11.18 and PostgreSQL 17.12. See the [verification and launch logs](evaluation/full-v4).

```bash
RUN_DIR=$(mktemp -d)
backend/.venv/bin/python scripts/verify.py --output "$RUN_DIR/verification.json"
```

### System architecture

![FitPilot system architecture](docs/fitpilot-architecture.svg)

The coordinator loads the signed-in user’s profile, activity, and saved pose summary. It runs Goal planning → Exercise planning → Nutrition → Exercise feedback, validates the assembled draft, then runs Evaluation and adaptation. The user reviews the draft before approval. Changing preferences or recording progress supplies context for a new draft.

MediaPipe runs in the browser. Saved measurements such as repetition count, angles, and confidence enter the feedback stage as structured data. Webcam frames and uploaded clips stay in the browser. The live model receives relevant profile and activity context through FastAPI.

| Where to look | Responsibility |
| --- | --- |
| [Coordinator and agents](backend/app/agents.py) | Stage order, shared context, catalog filtering, targeted revisions, and draft validation |
| [API and persistence](backend/app/main.py) | `POST /api/workflows/plan` creates a draft. `POST /api/plans` approves it. PostgreSQL stores plans and execution history. |
| [Pose tracker](frontend/src/PoseCoach.tsx) | Browser inference, repetition estimates, and explicit session saving |
| [Evaluation runner](scripts/evaluate.py) | Scenario inputs, baseline prompts, trace capture, and pass/fail scoring |

### Test cases and scoring

| Suite | Data | Metric |
| --- | --- | --- |
| Planning | [20 synthetic profiles](evaluation/planning_cases.json), including two infeasible menus | Valid draft rate on feasible trials and explicit rejection rate on infeasible trials |
| Adaptation | [10 profile changes](evaluation/adaptation_cases.json) with validated prior plans, including two infeasible changes | Valid replan rate and repair rate when the prior plan breaks the new constraints |
| Feedback | A missing session and two synthetic pose summaries in [the feedback runner](scripts/evaluate_feedback.py) | Returned metric consistency and a confidence note when measurements are absent or low confidence |

The live comparison uses the same case inputs and final validator for the five specialists, a one-call generalist, and a generalist with one revision. The validator checks schedule, session time, exercise eligibility, dietary compatibility, catalog facts, weekly servings, and budget. The traces include model responses, specialist stage order and status, validation, latency, calls, and tokens. See the [scoring methodology](docs/EVALUATION.md).

### Representative live cases

| Case | Input and check | Observed result in the clean v4 run |
| --- | --- | --- |
| P02 | Respect exact workout days and a USD 70 food budget. | Repeat 1 scheduled Tuesday and Saturday for 35 minutes each, selected 21 servings for USD 67.90, and passed all seven checks. |
| P19 | Report infeasibility for a USD 0 food budget. | All three specialist repeats stopped at Nutrition before requesting a model response for that stage. |
| A05 | Change a previously valid plan to vegan meals. | Repeat 1 replaced the incompatible menu with 11 chickpea rice bowls and 10 lentil tomato soups for USD 47.10. The draft passed. |
| Feedback | Preserve four squat reps and mean confidence 0.43. | The API returned the measurements with a low-visibility note. The test uses a synthetic summary. |

### Why the generalist baselines missed feasible plans

In the [54 feasible planning trials per method](evaluation/full-v4/planning.json), the one-call baseline returned an infeasibility signal with an empty menu all 54 times. The revision baseline did that in 50 final drafts. Its other four drafts supplied meals but failed the budget check through an incorrect total, an over-budget menu, or both. The trials had no baseline transport errors or final JSON parsing failures.

P02 repeat 1 makes the difference concrete. The one-call baseline returned `NO_COMPATIBLE_MENU`. The revision baseline treated the five listed recipes as insufficient for 21 servings. Its input supplied recipe facts with one serving per row. The specialist chose three compatible recipes at seven servings each and stayed under USD 70. This trace points to serving allocation as one failure mode. The experiment compares the full workflows, so it cannot isolate agent count from catalog filtering, constrained menu selection, and validation.

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

To rerun the reported trials, set up the [exact evaluated v4 checkout](docs/REPRODUCIBILITY.md#run-from-the-exact-evaluated-source). Connect through the [TACC setup guide](backend/tacc/README.md). If using the launcher's SSH tunnel, keep the launcher running in the first terminal. In a second terminal, enter the v4 repository root and export `TEST_DATABASE_URL` as in the smoke test. The live smoke test checks all five stages, approval, and readback. Replace the example URL if your endpoint uses a different address.

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

### Recorded evaluation results

Use the [clean v4 Tables 1–5](evaluation/full-v4/tables.md) and [original run tables](evaluation/results/tables.md) to locate each result. The [full run evidence](evaluation/full-v4) includes all 270 trial traces and the [side-by-side scores](evaluation/full-v4/comparison.md).

| Reference | Original run | Fresh clean v4 run |
| --- | --- | --- |
| Table 1 · Planning | Specialists 52/54. One call 0/54. Revision 0/54. Specialists rejected 6/6 infeasible trials. | Specialists 53/54. One call 0/54. Revision 0/54. Specialists rejected 6/6 infeasible trials. |
| Table 2 · Adaptation | Specialists 24/24. One call 1/24. Revision 3/24. Specialists rejected 6/6 infeasible trials. | Specialists 22/24. One call 1/24. Revision 4/24. Specialists rejected 6/6 infeasible trials. |
| Tables 3 and 4 · Cost and outcomes | Planning median 75.3 s for specialists, 27.8 s for one call, and 46.8 s for revision. | Planning median 64.2 s for specialists, 27.3 s for one call, and 51.1 s for revision. See the fresh tables for spread, tokens, and failure counts. |
| Table 5 · Stage flow | All five stages completed in 52/54 feasible planning and 24/24 feasible adaptation trials. | All five stages completed in 53/54 feasible planning and 22/24 feasible adaptation trials. |

The [fresh feedback API record](evaluation/full-v4/feedback.json) passed 3/3 synthetic summary cases.

In planning, specialists averaged 4.70 model calls per attempt versus 1.00 for one call and 1.90 with revision. They completed 53 of 54 feasible drafts, while both baselines completed none. The extra calls and higher median latency are the measured price of the constraint pass rate on this case bank. This fits a user-initiated weekly planning task where the user reviews a draft before saving. We did not measure acceptable wait time in a user study.

### Limitations and expected variation

- The live results apply to these synthetic cases, prompts, catalog, validators, and course Qwen configuration. The specialist workflow also uses catalog logic and structured stages, so the comparison cannot isolate the effect of agent count.
- Treat the recorded rates as reference points. Compare feasible pass rates, explicit rejections, and stage completion. Model outputs and token use vary with sampling. Network and GPU load affect latency. The report includes per-repeat counts and latency spread.
- Live reruns require authorized access to the course model or a reachable substitute. A different model can change the results. The local smoke test and recorded tables can be checked independently of that access.
- The pose tests use synthetic landmarks and the feedback API uses synthetic summaries. Real-video pose accuracy and rep-count error remain unmeasured. See the [pose protocol](docs/POSE.md) for a labeled-video assessment.

See the [implementation guide](docs/IMPLEMENTATION.md), [API reference](docs/API.md) and [database guide](docs/DATABASE.md) for system details. This README follows the [NSDI ’27 artifact instructions](https://www.usenix.org/conference/nsdi27/call-for-artifacts).
