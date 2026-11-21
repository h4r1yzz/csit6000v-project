# FitPilot

A personal fitness and wellness web application for CSIT6000V. FitPilot combines a React dashboard, browser pose estimation, a FastAPI multi-agent coordinator, TACC Qwen or OpenAI-compatible inference for planning and coaching, and a local SQLite database.

## Getting Started Instructions

### What is implemented

- Profile preferences covering goals, experience, workout frequency, time, schedule, equipment, diet, allergies, limitations, and meal budget.
- A central planning coordinator and five specialist agents: goal planning, exercise planning, nutrition, exercise feedback, and evaluation/adaptation.
- Individual agent execution, structured outputs, saved run history, and coordinated workout/meal drafts with explicit constraint checks.
- Review and approval before a generated plan becomes active. Generating or discarding a draft does not replace the approved plan.
- A dashboard with scheduled workouts and rest days, movement journal, workout logging, saved plan history, recoverable recent drafts, and persisted progress used for later planning.
- A coaching-team map with individual agent queries, readable structured results, run history, and visible model provenance.
- Webcam and uploaded-video pose tracking for squats, bicep curls, and arm circles, including landmarks, repetition counting, confidence, joint measurements, saved summaries, and up to eight numerical landmark snapshots per session.
- Coach chat with persisted/restored messages and OpenAI-compatible model integration. Planning, specialist agents and coach chat require a reachable model; failures are shown explicitly.
- SQLite persistence for profile, catalogs, plans, workouts, workflows, agent runs, pose sessions, and coach messages.

### Local setup

Install Git, Python 3.10 or later, and Node.js 22.18 or later with npm (required for the pose test suite). Python 3.12 was used for the recorded checks. Allow internet access for dependency installation, free ports below, and a browser with webcam/video support. No local GPU is required for the API; live inference requires a reachable model service. TACC GPU/account prerequisites are in the linked guide. FitPilot uses ports `5173` for the frontend and `8000` for the API.

Clone the repository and enter the project folder. If you already have a checkout, start with the dependency commands below.

```bash
git clone https://github.com/h4r1yzz/csit6000v-project.git
cd csit6000v-project
```

#### macOS and Linux

Install dependencies from the project root and start both services.

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
python3 scripts/dev.py
```

If `backend/.venv` already exists, reuse it and start with the dependency install command.

#### Windows PowerShell

Install dependencies from the project root.

```powershell
py -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt tzdata
npm.cmd ci --prefix frontend
```

Start the API in one PowerShell terminal from the project root.

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second PowerShell terminal from the project root.

```powershell
npm.cmd run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

#### Open FitPilot

Open the [FitPilot dashboard](http://127.0.0.1:5173) after both services start. For the backend, open the [interactive API reference](http://127.0.0.1:8000/docs). Press Ctrl+C in each terminal you started to stop the services.

Choose **Create account** with your name, email and password, then save your goals, diet, equipment and schedule under **Preferences**. Returning users can choose **Sign in**. Each account has its own profile, plans, workouts, conversations and prompt history. Configure a reachable model using the instructions below before generating plans, running agents or using coach chat. Without it these requests return HTTP 503; account, catalog, logging and browser pose functionality remain available.

#### Run in separate terminals on macOS or Linux

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

The development UI proxies API requests to FastAPI.

### MCP server (tool access for Cursor / hosts)

FitPilot exposes the same orchestrator tools over MCP stdio:

```bash
backend/.venv/bin/python backend/mcp_server.py
```

Example Cursor MCP config:

```json
{
  "mcpServers": {
    "fitpilot": {
      "command": "/absolute/path/to/csit6000v-project/backend/.venv/bin/python",
      "args": ["/absolute/path/to/csit6000v-project/backend/mcp_server.py"]
    }
  }
}
```

Coach chat uses the tool-calling orchestrator automatically when `LLM_BASE_URL` / TACC is configured.

### Connect an LLM

Copy `backend/.env.example` to `backend/.env` and edit it locally. `scripts/dev.py` automatically passes this file to Uvicorn. For separate backend startup, add `--env-file .env`. A bare `uvicorn` command does not automatically load `.env`.

Generic OpenAI-compatible service:

```dotenv
LLM_BASE_URL=http://YOUR_MODEL_HOST:8000/v1
LLM_MODEL=YOUR_MODEL_NAME
LLM_API_KEY=
```

#### Use course TACC Qwen

The dashboard, webcam and video analysis, FastAPI backend, agents, and SQLite database run on your computer. TACC supplies Qwen inference through a GPU job. Start the local app with the setup above and follow the course connection steps. [TACC setup guide](backend/tacc/README.md)

Run `python3 scripts/dev.py --tacc-job SERVICE_JOB_ID` through a TACC gateway that permits SSH forwarding. Replace `SERVICE_JOB_ID` with the running GPU job ID. A directly reachable endpoint can also be configured as `QWEN_BASE_URL` in `backend/.env`. Use `/api/model/status` to verify the connection. [Connect the local app](backend/tacc/README.md#4-connect-your-local-app)

The guide also includes an optional CPU validation job. It checks all five agents from inside TACC using synthetic data and saves a downloadable JSON result.

### Small end-to-end check (simulated model, no credentials)

After setup, run from the repository root:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/python scripts/smoke.py
```

On Windows replace `backend/.venv/bin/python` with `.\backend\.venv\Scripts\python.exe`.
Expected output:

```text
PASS: account -> five simulated model stages -> valid draft -> approval -> persisted active plan
SIMULATED MODEL: this checks application integration, not live inference or recommendation quality.
```

This uses an isolated temporary database, real API routes, validation and persistence, with only the model transport simulated. It does not contact a model or change your application data. Setup plus this check should normally fit within 30 minutes, subject to dependency downloads.

### Small live example

Configure the model first. Start the app, create an account, and retain the default four-day, 35-minute beginner profile with bodyweight/dumbbells, high-protein meals and USD 70 budget. Generate a weekly plan. Expected: five completed specialist stages, a valid draft with four workouts and 21 weekly meal servings, and model provenance (`llm` or `tacc_qwen`). No plan is active until you approve it. Approve, reload, and verify the active plan persists. Exact wording and exercise choices may vary. A 503 response is a failed model run, not a successful local fallback. Allow up to several minutes for the workflow; TACC startup/queue time is additional.

## Detailed Instructions

### Build and verify

```bash
(cd frontend && npm run build)
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
(cd backend && .venv/bin/python -m unittest discover -s tests -v)
```

With Node.js 22.18 or later, you can also run the pose analyzer tests with `node --test frontend/src/pose/analysis.test.mjs` from the project root.

FastAPI can serve the built frontend when `frontend/dist` exists at startup; the Vite development server is not required for that mode. See [manual verification](#manual-verification) for webcam, clip, persistence, and agent checks.

### Reproduce the evaluation

Run all deterministic checks, saving logs and a machine-readable summary:

```bash
backend/.venv/bin/python scripts/verify.py
```

Expected: `frontend_build`, `backend_tests`, `pose_tests`, and `api_smoke` each report `PASS`. Current recorded counts: 38 backend tests passed and 28 PostgreSQL tests skipped; 17 pose tests passed. PostgreSQL is an optional deployment integration and is not covered by the default SQLite verification. The optional PostgreSQL command is below.

Recorded implementation checks (2026-11-21, Asia/Hong_Kong):

| Check | Command (repository root) | Observed result |
| --- | --- | --- |
| Production frontend | npm run build --prefix frontend | Passed TypeScript and Vite build |
| Backend SQLite/API integration | cd backend && .venv/bin/python -m unittest discover -s tests -v | 38 passed; 28 PostgreSQL tests skipped; zero failures/errors |
| Synthetic pose analysis | node --test frontend/src/pose/analysis.test.mjs | 17 passed |
| Isolated end-to-end API | backend/.venv/bin/python scripts/smoke.py | Account, five simulated stages, draft validation, approval and persistence passed |

Raw logs and machine-readable results are in `evaluation/results/`. These are simulated-model and synthetic-landmark checks, not live inference, real-video accuracy, PostgreSQL integration or clean-machine installation results.

Live planning and baseline comparisons use `evaluation/planning_cases.json` (20 synthetic profiles). Replanning comparisons use `evaluation/adaptation_cases.json` (10 changes). Run a one-case connectivity trial before the full experiment:

```bash
backend/.venv/bin/python scripts/evaluate.py --env-file backend/.env --limit 1 --repeats 1 --modes multi_agent --output evaluation/results/live-smoke.json
backend/.venv/bin/python scripts/evaluate.py --env-file backend/.env --suite planning --repeats 3 --output evaluation/results/planning.json
backend/.venv/bin/python scripts/evaluate.py --env-file backend/.env --suite adaptation --repeats 3 --output evaluation/results/adaptation.json
```

These commands make real model calls and may consume service quota. The full comparison includes `multi_agent`, `single_call`, and `single_agent` (one generalist plus at most one validation-guided revision). Runs use disposable SQLite databases. Raw outputs, validation checks, failures, elapsed seconds and attempted model calls are saved after each case. Use new output filenames for reruns. An endpoint URL alone does not prove live availability.

Live result files and 15 labeled video clips have not yet been supplied or generated. Do not interpret the synthetic integration checks as real-video accuracy or model-quality measurements. Expected variation includes model generation, provider version, GPU queue/load, network latency, camera framing and hardware; report three repeats and the spread, not just a favorable run. There is no established numerical tolerance until the live/video evaluation is completed.

### Evaluation configuration and metrics

Use the README setup, Node 22.18+ and Python 3.10+ (recorded: Python 3.12). The frontend lockfile fixes npm dependencies. Python requirements use compatible version ranges; recorded installed versions are in evaluation/results/python-environment.txt. Record the exact model/version, hardware, provider, server launch options and runtime when executing live evaluations. TACC uses the supplied serve scripts and course account/archive; reviewers need their own authorized access. Never include private keys or .env contents in submitted artifacts.

The runner uses the configured model at temperature 0.2, a maximum of 2,200 tokens for specialist calls and 4,000 for baseline calls. Specialist constraint repair allows one additional attempt; single_call has none; single_agent has one generalist validation-guided revision. This difference in token budgets and prompt structure is a comparison limitation. Both baselines receive the same catalogs/profile/context; the multi-agent path also uses specialist prompts and prevalidated nutrition menu choices. Record and discuss this confound instead of attributing every difference solely to agent count.


Validate inputs without connecting to a model:

```bash
backend/.venv/bin/python scripts/evaluate.py --validate-only
backend/.venv/bin/python scripts/evaluate.py --suite adaptation --validate-only
```

Use the live commands above. The planning cases include varied days, duration, experience, equipment, diets, allergies, currencies, limitations, and two infeasible catalog/budget requests. The adaptation suite first generates an initial plan, then changes a constraint and reruns using the initial plan as context. Failed initial plans remain failures, not silently omitted observations.

Definitions:

- Valid-plan rate: runs whose generated plan passes every implemented deterministic check, divided by all attempted runs in the selected subset. Report feasible and infeasible cases separately.
- Expected-outcome rate: valid plan for a feasible case; returned invalid validation for an infeasible case. Exceptions/timeouts never count as successful rejection. The application's explicit exception-based rejection may be correct, but must be adjudicated manually from traces; the automated rate is conservative.
- Latency: wall time around plan generation/validation. Adaptation records initial generation separately; reported summary latency is the replan stage only. Include initial time if reporting total scenario cost.
- Model calls: attempted transport calls, including failed calls and revisions. Initial and replan counts are separate.
- Token usage: sums provider-reported prompt, completion and total tokens across calls. If any attempted call lacks valid usage (including a transport failure), the total is null rather than zero.
- Adaptation: automatic validation checks the new constraints. It does not score correct agent selection, quality of explanations, or preservation of unaffected plan details. Review these separately against a written rubric.

Use at least three repeats per case/model/mode. Keep all raw results, failures, model settings and repetitions. Report distributions/ranges as well as means or medians. Exact generated text is not expected to match. No numerical acceptance tolerance is established yet. A completed runner exits successfully even when individual model runs fail: inspect the JSON metrics and errors, not only its process exit code.

### Optional PostgreSQL verification

To test the optional PostgreSQL deployment, use a dedicated disposable database with no production data:

```bash
cd backend
TEST_DATABASE_URL='postgresql://USER:PASSWORD@HOST/DISPOSABLE_DB' .venv/bin/python -m unittest discover -s tests -p test_postgres.py -v
```

The inherited integration suite creates and removes schemas, including account schemas. Do not point it at a shared or production database. It is excluded from the default verification run.

### Video evaluation

The course announcement does not prescribe a clip count. The following 15-clip protocol comes from our proposal and is needed if the final report claims results from that evaluation. No real-video accuracy result is currently claimed.

Record 15 consented clips, five each for squat, bicep curl and arm circles. Include ordinary movement, incomplete reps, obscured joints and difficult camera framing. Give files stable IDs and record checksums, exercise, duration, frame rate, dimensions, camera view, browser/device, calibration state, expected repetitions and expected cues/repositioning prompts. Label expectations before viewing system predictions.

For each clip: open Form check, select the exercise, load the clip, reset the session, apply the documented calibration policy, play once from beginning to end, and export/record the derived summary. Curls count each arm separately: a simultaneous bilateral curl counts as two. Compare predicted cues and repetition totals with the labels; report cue-check pass proportion and rep absolute error. Save failures and low-confidence cases. Use at least two reviewers for subjective feedback quality and record disagreements.

The runner does not execute MediaPipe on videos. Real clips, annotations, browser observations and measurements must be supplied by the group. Synthetic landmark unit tests are not a substitute. Keep reproducible clips available to graders through an authorized stable download if they cannot be committed.

### Final report mapping

| Report result | Input / command | Current status |
| --- | --- | --- |
| Implementation checks above | scripts/verify.py | Recorded |
| Planning/constraint comparison table | planning_cases.json; evaluate.py --suite planning | Live runs and final report table number pending |
| Adaptation comparison table | adaptation_cases.json; evaluate.py --suite adaptation | Live runs, manual rubric and report table number pending |
| Pose/cue accuracy figure or table | 15 labeled clips; browser protocol above | Clips, labels and measurements pending |
| Latency/model-call/token comparison | Raw live JSON plus provider usage logs | Live data and token logs pending |

Use actual final report figure/table numbers before submitting. Update README and regenerate the PDF after this mapping is complete.

### Manual verification

Configure a reachable model before exercising planning or coaching.

1. Start the API and UI with `python3 scripts/dev.py`. Open the UI at `http://127.0.0.1:5173` and API documentation at `http://127.0.0.1:8000/docs`.
2. Create an account or sign in, then open preferences. Save a name, goal, experience, number of workout days, session duration, equipment, schedule, food preferences/allergies, limitations, and meal budget. Reload and confirm the saved values remain.
3. Build a weekly plan. Review the coordinator steps and result sources. Confirm no plan is active until approval. Inspect workout count, selected days, session lengths, equipment, diet/allergies, and estimated meal cost.
4. Approve a valid draft and reload. Confirm it is active. Generate another draft and discard it; confirm the previous plan is still active.
5. Run each specialist in the agent workspace. Inspect its structured output and the execution history. Run evaluation after logging recent activity and inspect its progress assessment.
6. Log a workout with duration and effort. Confirm the dashboard and movement journal update, and that they persist after reload.
7. Open the form tracker. Choose a squat, curl, or arm circle. Start the webcam, allow access, and check that the video and skeleton align. Confirm no reps are counted while the relevant joints are outside the frame or insufficiently visible.
8. Stop the webcam and confirm the browser camera indicator turns off. Switch exercises and reset the session; confirm rep and movement state reset together.
9. Select a local clip, play/pause it, seek or replay it, and confirm there is only one active inference loop. Switch sources and confirm old media resources are released.
10. Save a completed pose session. Confirm the saved measurements appear in history and can be reviewed by the feedback agent. Check the browser network panel: requests must contain summary data, not video bytes or image frames.
11. Block camera permissions and check the actionable error. Disable model/WASM access and check that pose initialization fails visibly rather than silently counting reps.
12. Stop the API and try saving or running an agent. Confirm a visible error and no false success confirmation. Restart it and retry.


With no LLM URL set, planning, specialist agents and chat must return HTTP 503 with a configuration error. With a reachable compatible endpoint, confirm successful results identify live inference. Point the backend at an unreachable endpoint and confirm visible failure without a fabricated plan or local answer.

Use a mock compatible endpoint for repeatable tests of malformed JSON, HTTP failures, and invalid constraints. A model's natural-language assertion that a plan is safe is not a substitute for application validation.


### Documentation

- [Implementation and architecture](docs/IMPLEMENTATION.md): implemented components, agent workflow, scope, and extension points.
- [API and environment reference](docs/API.md): routes, schemas, model configuration, and examples.
- [Pose tracker guide](docs/POSE.md): inference, confidence filters, repetition rules, and save lifecycle.
- [Database guide](docs/DATABASE.md): tables, migrations, backups, and persistence.

### Project layout

| Path | Purpose |
| --- | --- |
| `frontend/` | React, TypeScript, Vite, MediaPipe browser tracking |
| `backend/` | FastAPI, typed agent workflows, model client, persistence adapter |
| `database/` | SQLite schema and curated exercise/recipe seeds |
| `docs/` | Technical implementation, API, pose, database, and deployment guides |
| `scripts/dev.py` | Local API and frontend process supervisor |
| `Proposal/` | Original course proposal, retained as reference |
| `Samples/` | Course-provided TACC examples, retained locally |

### Scope and limits

FitPilot uses password login and a private workspace per account. Existing pre-login demo records remain in their original store. New accounts start with fresh histories. General wellness suggestions and heuristic pose cues are not a clinical assessment.

Video remains in the browser. Saving sends derived movement summaries and up to eight numerical 33-landmark snapshots to FastAPI; enabling an LLM sends relevant profile and movement context to that configured service. MediaPipe loads model/WASM assets from the app itself. The Lite model is bundled in frontend/public/models, and npm run dev/build copies WASM files from the installed package. Webcam access requires localhost or HTTPS, browser permission, and compatible hardware. Live TACC inference and camera performance must be verified on the intended device and network.

### Vercel + Neon deployment

See [the deployment guide](docs/DEPLOY-VERCEL.md) for Neon connection settings, existing SQLite data transfer, Vercel setup, and MediaPipe checks.
