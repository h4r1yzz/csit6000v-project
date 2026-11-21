# FitPilot

CSIT6000V course project: a personal fitness web app with a React UI, FastAPI multi-agent planner, browser pose tracking, and optional TACC Qwen / OpenAI-compatible inference. This README follows the [NSDI ’27 Call for Artifacts](https://www.usenix.org/conference/nsdi27/call-for-artifacts) structure required by the course.

Repository: https://github.com/h4r1yzz/csit6000v-project

Pinned grading revision: [grading-submission-2026-11-21](https://github.com/h4r1yzz/csit6000v-project/tree/grading-submission-2026-11-21)

## Getting Started Instructions

Use this section to install FitPilot and confirm basic functionality within about 30 minutes (excluding slow dependency downloads).

### Prerequisites

- Git
- Python 3.10+ (recorded checks used Python 3.12)
- Node.js 22.18+ with npm (required for the pose unit tests)
- Free local ports `5173` (UI) and `8000` (API)
- Internet access to install dependencies
- macOS or Linux for the recorded one-command launcher (`scripts/dev.py`)
- A Neon (or other Postgres) database URL for `DATABASE_URL` (prefer a disposable branch for tests)

No local GPU is required for setup or the simulated end-to-end check. Live planning and coaching need a reachable model endpoint (course TACC Qwen or another OpenAI-compatible service).

### Setup

```bash
git clone https://github.com/h4r1yzz/csit6000v-project.git
cd csit6000v-project

python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
```

Copy `backend/.env.example` to `backend/.env` and set `DATABASE_URL` (required). Optionally set `QWEN_BASE_URL` or `LLM_BASE_URL` for a model. `scripts/dev.py` loads that file automatically. Without a reachable model, account/catalog/pose features still work; plan generation, specialist agents, and coach chat return HTTP 503.

Start the API and UI:

```bash
python3 scripts/dev.py
```

Then open http://127.0.0.1:5173 (UI) and http://127.0.0.1:8000/docs (API). Stop with Ctrl+C.

For TACC Qwen through the course gateway (after a GPU serve job is running):

```bash
python3 scripts/dev.py --tacc-job SERVICE_JOB_ID
```

Details: [`backend/tacc/README.md`](backend/tacc/README.md).

### Small end-to-end example

From the repository root, after setup:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
# Uses TEST_DATABASE_URL or DATABASE_URL; creates a disposable schema then drops it.
backend/.venv/bin/python scripts/smoke.py
```

Expected output:

```text
PASS: account -> five simulated model stages -> valid draft -> approval -> persisted active plan
SIMULATED MODEL: this checks application integration, not live inference or recommendation quality.
```

This uses an isolated Postgres schema and real API routes. Only the model transport is simulated. It does not contact a live model. Prefer a disposable Neon branch so smoke/verify do not share production data.

## Detailed Instructions

Use this section to rerun the evaluation that supports the repository artifact claims.

### Recorded deterministic evaluation

Reproduce the checks recorded in `evaluation/results/`:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
# Export DATABASE_URL or TEST_DATABASE_URL first (disposable Neon branch recommended).
backend/.venv/bin/python scripts/verify.py
```

`scripts/verify.py` runs:

| Check | Command | Expected |
| --- | --- | --- |
| Frontend build | `npm run build --prefix frontend` | Exit 0 |
| Backend tests | `cd backend && .venv/bin/python -m unittest discover -s tests -v` | Pass (requires `DATABASE_URL` / `TEST_DATABASE_URL`) |
| Pose unit tests | `node --test frontend/src/pose/analysis.test.mjs` | Pass |
| API smoke | `backend/.venv/bin/python scripts/smoke.py` | `PASS: account -> five simulated model stages...` |

Recorded run (2026-11-21, Python 3.11.18, local PostgreSQL; see `evaluation/results/verification.json`):

- `frontend_build`: PASS
- `backend_tests`: 43 passed, 0 skipped, 0 failures
- `pose_tests`: 17 passed
- `api_smoke`: PASS

Logs: `evaluation/results/*.log`. The verification run uses a disposable PostgreSQL schema and simulated model responses. It checks software integration and synthetic pose calculations, not live model quality or real-video accuracy.

Validate evaluation case files without calling a model:

```bash
backend/.venv/bin/python scripts/evaluate.py --validate-only
backend/.venv/bin/python scripts/evaluate.py --suite adaptation --validate-only
```

Expected: a `PASS` line confirming the planning or adaptation cases satisfy the profile schema.

### Test cases, data, and configurations

| Artifact | Path | Role |
| --- | --- | --- |
| Planning cases | `evaluation/planning_cases.json` | 20 synthetic profiles (schedule, duration, equipment, diet, allergies, currency, two infeasible catalog/budget cases) |
| Adaptation cases | `evaluation/adaptation_cases.json` | 10 constraint-change scenarios after an initial plan |
| Smoke / verify runner | `scripts/smoke.py`, `scripts/verify.py` | Deterministic integration checks |
| Live comparison runner | `scripts/evaluate.py` | Real model calls for planning/adaptation suites |
| Live feedback checks | `scripts/evaluate_feedback.py` | Signed-in feedback endpoint with missing, low-confidence and clear synthetic pose summaries |
| Recorded verify outputs | `evaluation/results/` | Logs + `verification.json` from the recorded deterministic run |
| Default app config | `backend/.env.example` | Required `DATABASE_URL`, model URL, timeouts, timezone, CORS |

Live evaluation (requires a reachable model and `TEST_DATABASE_URL` or `DATABASE_URL` pointing to a disposable Postgres database):

```bash
export TEST_DATABASE_URL='postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require'
export QWEN_BASE_URL='http://127.0.0.1:18000/v1' # example: a live endpoint or local TACC SSH tunnel
export QWEN_MODEL='qwen3.8-27b'
backend/.venv/bin/python scripts/evaluate.py --suite planning --repeats 3 --workers 4 --output evaluation/results/planning.json
backend/.venv/bin/python scripts/evaluate.py --suite adaptation --repeats 3 --workers 4 --output evaluation/results/adaptation.json
backend/.venv/bin/python scripts/summarize_evaluation.py --output evaluation/results/tables.md
```

The planning run makes 180 scenario attempts (20 cases × 3 methods × 3 repeats); adaptation makes 90. The checked-in live runs use TACC Qwen `qwen3.8-27b`. Planning results are assembled from per-method runs so the corrected generalist revision and explicit specialist-stage traces are retained. `planning.json` records each method's runner hash. The live runner checkpoints every attempt; add `--resume` with the same arguments after interruption. These commands consume model quota. A successful process exit means the experiment finished, not that every draft passed; inspect the raw outputs and generated tables.

The recorded live planning results show 52/54 feasible drafts passing all checks for the five-specialist workflow, 52/54 completing all five specialist stages, and 6/6 infeasible cases correctly stopping at nutrition. The one-call and generalist-plus-revision baselines passed 0/54 feasible trials each and explicitly recognized 3/6 infeasible cases each. For adaptation, the specialist workflow passed 24/24 feasible cases and correctly rejected 6/6 infeasible cases. Tables 1–5 and the methodology are in [`docs/EVALUATION.md`](docs/EVALUATION.md); raw traces, latency, token and flow records are in `evaluation/results/`.

`evaluate_feedback.py` also passed 3/3 live API cases using synthetic pose summaries. It checks missing measurements, a low-confidence summary and a clear-view summary, including the metrics returned to the model. No labeled workout video was supplied, so the repository makes no real-video pose-accuracy claim.

### Mapping to the project report

The final course report was not present in the supplied checkout, so page numbers cannot be cross-referenced here. Cite the report-ready tables in [`docs/EVALUATION.md`](docs/EVALUATION.md) and map those table numbers into the final course report.

| Claim / result in report | How to reproduce | Status in this artifact |
| --- | --- | --- |
| Implementation / integration checks | `scripts/verify.py` | Recorded in `evaluation/results/` |
| Planning / constraint comparison | `evaluation/planning_cases.json` + `scripts/evaluate.py --suite planning` | Tables 1, 3, 4, 5 in `docs/EVALUATION.md`; raw cases/traces in `evaluation/results/planning*.json` |
| Adaptation comparison | `evaluation/adaptation_cases.json` + `scripts/evaluate.py --suite adaptation` | Tables 2, 3, 4, 5 in `docs/EVALUATION.md`; raw traces in `evaluation/results/adaptation.json` |
| Pose feedback API behavior | `scripts/evaluate_feedback.py` | Three live synthetic-summary cases in `evaluation/results/feedback.json`; not a video-accuracy result |
| Pose / cue accuracy on real video | Browser Form check protocol in `docs/POSE.md` | Not measured; no labeled workout clips were provided |
| Latency / token / model-call tables | Live `evaluate.py` JSON + provider usage | Table 3 in `docs/EVALUATION.md` and `evaluation/results/tables.md` |

### Known limitations and expected variation

- Planning, specialist agents, and coach chat **require** a configured reachable model. There is no local-rules substitute; failures return HTTP 503.
- Graders need their own authorized TACC (or other model) access for live runs. Endpoint URL alone does not prove availability.
- Simulated smoke/verify results are not model-quality or real-video accuracy measurements.
- Live model text, exercise choices, latency, and token counts vary with provider version, GPU queue, network, and sampling. Use at least three repeats and report spread when claiming live results.
- Exact generated wording is not expected to match across runs. Constraint pass rates and output/error counts are the primary metrics; timing and tokens are descriptive and vary with provider version, GPU queue, network, and sampling.
- Neon/Postgres is required for the app and for smoke/verify. Deployment notes: `docs/DEPLOY-VERCEL.md`.

### Further documentation

Architecture, API, pose tracker, database, and deployment details: `docs/IMPLEMENTATION.md`, `docs/API.md`, `docs/POSE.md`, `docs/DATABASE.md`, `docs/DEPLOY-VERCEL.md`.

## Group contributions

- **Harry Chandra Tsjan (21340623):**
- **Allabonu Sri Harsha Lakshman (21344461):**
- **Nehanth Kasi Geetha (21386988):**
