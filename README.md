# FitPilot

A personal fitness and wellness web application for CSIT6000V. FitPilot combines a React dashboard, browser pose estimation, a FastAPI multi-agent coordinator, optional TACC Qwen inference, and a local SQLite database.

## What is implemented

- Profile preferences covering goals, experience, workout frequency, time, schedule, equipment, diet, allergies, limitations, and meal budget.
- A central planning coordinator and five specialist agents: goal planning, exercise planning, nutrition, exercise feedback, and evaluation/adaptation.
- Individual agent execution, structured outputs, saved run history, and coordinated workout/meal drafts with explicit constraint checks.
- Review and approval before a generated plan becomes active. Generating or discarding a draft does not replace the approved plan.
- A dashboard with scheduled workouts and rest days, movement journal, workout logging, saved plan history, recoverable recent drafts, and persisted progress used for later planning.
- A coaching-team map with individual agent queries, readable structured results, run history, and visible model/local provenance.
- Webcam and uploaded-video pose tracking for squats, bicep curls, and arm circles, including landmarks, repetition counting, confidence, joint measurements, saved summaries, and up to eight numerical landmark snapshots per session.
- Coach chat with persisted/restored messages and optional OpenAI-compatible model integration. Local fallback results remain usable without a model service and are labeled accordingly.
- SQLite persistence for profile, catalogs, plans, workouts, workflows, agent runs, pose sessions, and coach messages.

## Local setup

Install Git, Python 3.10 or later, and Node.js 20 or later with npm. FitPilot uses ports `5173` for the frontend and `8000` for the API.

Clone the repository and enter the project folder. If you already have a checkout, start with the dependency commands below.

```bash
git clone https://github.com/h4r1yzz/csit6000v-project.git
cd csit6000v-project
```

### macOS and Linux

Install dependencies from the project root and start both services.

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
python3 scripts/dev.py
```

If `backend/.venv` already exists, reuse it and start with the dependency install command.

### Windows PowerShell

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

### Open FitPilot

Open the [FitPilot dashboard](http://127.0.0.1:5173) after both services start. For the backend, open the [interactive API reference](http://127.0.0.1:8000/docs). Press Ctrl+C in each terminal you started to stop the services.

Choose **Create account** with your name, email and password, then save your goals, diet, equipment and schedule under **Preferences**. Returning users can choose **Sign in**. Each account has its own profile, plans, workouts, conversations and prompt history. You can generate plans and query agents using local rules without creating a `.env` file or configuring a model account.

### Run in separate terminals on macOS or Linux

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

The development UI proxies API requests to FastAPI.

## MCP server (tool access for Cursor / hosts)

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

## Connect an LLM

Copy `backend/.env.example` to `backend/.env` and edit it locally. `scripts/dev.py` automatically passes this file to Uvicorn. For separate backend startup, add `--env-file .env`. A bare `uvicorn` command does not automatically load `.env`.

Generic OpenAI-compatible service:

```dotenv
LLM_BASE_URL=http://YOUR_MODEL_HOST:8000/v1
LLM_MODEL=YOUR_MODEL_NAME
LLM_API_KEY=
```

### Use course TACC Qwen

The dashboard, webcam and video analysis, FastAPI backend, agents, and SQLite database run on your computer. TACC supplies Qwen inference through a GPU job. Start the local app with the setup above and follow the course connection steps. [TACC setup guide](backend/tacc/README.md)

Run `python3 scripts/dev.py --tacc-job SERVICE_JOB_ID` through a TACC gateway that permits SSH forwarding. Replace `SERVICE_JOB_ID` with the running GPU job ID. A directly reachable endpoint can also be configured as `QWEN_BASE_URL` in `backend/.env`. Use `/api/model/status` to verify the connection. [Connect the local app](backend/tacc/README.md#4-connect-your-local-app)

The guide also includes an optional CPU validation job. It checks all five agents from inside TACC using synthetic data and saves a downloadable JSON result.

## Build and verify

```bash
(cd frontend && npm run build)
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
(cd backend && .venv/bin/python -m unittest discover -s tests -v)
```

With Node.js 22.18 or later, you can also run the pose analyzer tests with `node --test frontend/src/pose/analysis.test.mjs` from the project root.

FastAPI can serve the built frontend when `frontend/dist` exists at startup; the Vite development server is not required for that mode. See [manual verification](docs/QA.md) for webcam, clip, persistence, and agent checks.

## Documentation

- [Implementation and architecture](docs/IMPLEMENTATION.md): implemented components, agent workflow, scope, and extension points.
- [API and environment reference](docs/API.md): routes, schemas, model configuration, and examples.
- [Pose tracker guide](docs/POSE.md): inference, confidence filters, repetition rules, and save lifecycle.
- [Database guide](docs/DATABASE.md): tables, migrations, backups, and persistence.
- [Verification guide](docs/QA.md): automated commands, manual walkthrough, and remaining evaluation work.
- [Recorded verification](docs/VERIFICATION.md): checks actually completed and current verification limits.

## Project layout

| Path | Purpose |
| --- | --- |
| `frontend/` | React, TypeScript, Vite, MediaPipe browser tracking |
| `backend/` | FastAPI, typed agent workflows, model client, persistence adapter |
| `database/` | SQLite schema and curated exercise/recipe seeds |
| `docs/` | Implementation, API, database, and verification documentation |
| `scripts/dev.py` | Local API and frontend process supervisor |
| `Proposal/` | Original course proposal, retained as reference |
| `Samples/` | Course-provided TACC examples, retained locally |

## Scope and limits

FitPilot uses password login and a private workspace per account. Existing pre-login demo records remain in their original store. New accounts start with fresh histories. General wellness suggestions and heuristic pose cues are not a clinical assessment.

Video remains in the browser. Saving sends derived movement summaries and up to eight numerical 33-landmark snapshots to FastAPI; enabling an LLM sends relevant profile and movement context to that configured service. MediaPipe loads model/WASM assets from the app itself. The Lite model is bundled in frontend/public/models, and npm run dev/build copies WASM files from the installed package. Webcam access requires localhost or HTTPS, browser permission, and compatible hardware. Live TACC inference and camera performance must be verified on the intended device and network.

## Vercel + Neon deployment

See [the deployment guide](docs/DEPLOY-VERCEL.md) for Neon connection settings, existing SQLite data transfer, Vercel setup, and MediaPipe checks.
