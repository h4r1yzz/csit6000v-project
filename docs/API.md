# API and configuration reference

The local FastAPI base URL is `http://127.0.0.1:8000`. Interactive schemas and request forms are available at `/docs`; the machine-readable contract is `/openapi.json`. JSON request examples below assume that the development API is running.

## Environment variables

Put private values in `backend/.env`. Start with `python3 scripts/dev.py`, or run Uvicorn from `backend/` with `--env-file .env`. Process environment variables take precedence over `.env` values.

| Variable | Meaning |
| --- | --- |
| `LLM_BASE_URL` | Generic OpenAI-compatible API base including its API prefix, usually `/v1`. Takes precedence over `QWEN_BASE_URL`. |
| `LLM_MODEL` | Model identifier for the generic endpoint. Set it explicitly for the selected provider. |
| `LLM_API_KEY` | Optional bearer token sent by the backend only. |
| `LLM_TIMEOUT_SECONDS` | Per-request model timeout. Falls back to `QWEN_TIMEOUT_SECONDS`, then 45 seconds. Finite values are clamped to 1–120 seconds; invalid values use 45 seconds. |
| `QWEN_BASE_URL` | Course TACC Qwen service base including `/v1`. Used when `LLM_BASE_URL` is unset. |
| `QWEN_MODEL` | TACC model identifier; default `qwen3.8-27b`. |
| `QWEN_TIMEOUT_SECONDS` | Legacy TACC timeout setting. |
| `FITPILOT_DB_PATH` | SQLite file path. Default: project `database/fitpilot.db`. A relative path is resolved from the backend process working directory. |
| `FITPILOT_TIMEZONE` | Calendar timezone for progress calculations; default `Asia/Hong_Kong`. |
| `CORS_ORIGINS` | Comma-separated browser origins permitted to call the API. Defaults to the local Vite origins. |

Model base URLs must use HTTP or HTTPS and cannot contain embedded credentials, query strings, or fragments. The client appends `/chat/completions`; supply the provider's API base rather than its completions URL. Neither API keys nor model service URLs are needed in the React bundle.

Each specialist requires a configured model. A deterministic constraint failure allows one targeted revision. Unavailable services, malformed outputs or exhausted revisions fail the request (HTTP 503); no local agent answer replaces the failure. Workflow results can include clarification notes for broad or infeasible preferences. The connection probe uses an eight-second timeout.

## Routes

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account with name, email and password (8–128 characters), then start a session. |
| POST | `/api/auth/login` | Start a session using email and password. |
| GET | `/api/auth/me` | Get the signed-in account identity. |
| POST | `/api/auth/logout` | Revoke the current session. |
| GET | `/api/health` | API status and model configuration information. |
| GET | `/api/model/status` | Explicitly check the configured model service. |
| GET | `/api/profile` | Read the local profile. |
| PUT | `/api/profile` | Validate and replace profile preferences. |
| GET | `/api/overview` | Profile, weekly activity statistics, recent logs, and active plan. |
| GET | `/api/catalogs` | Read curated exercise/recipe facts and pricing notes. |
| GET | `/api/plans` | List saved plans. |
| POST | `/api/plans/generate` | Generate a coordinated draft; compatibility alias for the plan workflow. |
| POST | `/api/workflows/plan` | Run the coordinator and return a draft, specialist steps, and validation checks. |
| GET | `/api/workflows` | List persisted workflow records. |
| GET | `/api/workflows/{id}` | Retrieve workflow state and result. |
| POST | `/api/plans` | Validate and explicitly activate a reviewed plan. |
| GET | `/api/workouts` | Read workout journal entries. |
| POST | `/api/workouts` | Add a completed workout. |
| GET | `/api/agents` | List the specialist agent registry. |
| POST | `/api/agents/{agent_id}/run` | Run one specialist with current stored context. |
| GET | `/api/agent-runs` | Read persisted specialist runs. |
| GET | `/api/pose-sessions` | Read saved derived movement summaries. |
| POST | `/api/pose-sessions` | Save a movement summary; never accepts video. |
| GET | `/api/assistant/messages` | Read persisted coach conversation messages. |
| POST | `/api/assistant/chat` | Coach chat. With a configured model, uses the tool-calling orchestrator; pass `agent_id` to force one specialist. |
| GET | `/api/tools` | List shared FitPilot tool schemas used by the orchestrator. |
| POST | `/api/orchestrator/chat` | Run the tool-calling orchestrator explicitly. |
| POST | `/api/orchestrator/plan` | Run the specialist plan workflow through the orchestrator API. |

`/api/workflows`, `/api/agent-runs`, and `/api/pose-sessions` accept a `limit` query parameter (maximum 100). `/api/workouts` accepts a limit up to 1,000. `/api/agent-runs` also accepts an `agent_id` filter. History reads return recent records rather than an unbounded full export.

Personal data routes require a valid HTTP-only session cookie. Requests without one receive HTTP 401. Browser clients send it automatically on same-origin API calls. For the curl examples below, first sign in with a cookie jar and pass `-b cookies.txt` on subsequent requests. Keep the cookie jar private.

## Profile

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/profile
```

Update with a complete preference object:

```json
{
  "name": "Alex",
  "goal": "Build strength with a consistent routine",
  "experience": "beginner",
  "weekly_days": 3,
  "minutes_per_session": 30,
  "equipment": "bodyweight, dumbbells",
  "dietary_preferences": "vegetarian",
  "weekly_budget": 70,
  "scheduled_days": ["Monday", "Wednesday", "Friday"],
  "food_allergies": "peanut",
  "limitations": "",
  "budget_currency": "USD"
}
```

`scheduled_days` must be empty for automatic distribution or contain exactly `weekly_days` unique full English day names. `experience` is `beginner`, `intermediate`, or `advanced`. Workout frequency is 1–7 and session duration is 10–180 minutes. Currency is `USD` or `HKD`. Catalog costs are fixed USD estimates; HKD uses a fixed 7.8 HKD per USD planning conversion. These are not live food prices or exchange rates.

## Agent execution

Supported IDs: `goal_planning`, `exercise_planning`, `nutrition`, `exercise_feedback`, `evaluation_adaptation`.

```bash
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/agents/goal_planning/run \
  -H 'Content-Type: application/json' \
  -d '{"message":"Focus on a routine I can maintain."}'
```

Agent request fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `message` | string, up to 1,200 characters | Optional user question or request. |
| `pose_session_id` | positive integer | Optional saved movement summary for exercise feedback. |

An agent run contains `id`, `agent_id`, `status`, `source`, `output`, `created_at`, and optional `workflow_id`/`error`. `output` is agent-specific structured JSON. Failed runs retain an error and no successful generated output. Inspect `source` rather than assuming that a configured service generated the result.

## Coordinated draft and approval

```bash
curl -X POST http://127.0.0.1:8000/api/workflows/plan \
  -H 'Content-Type: application/json' -d '{}'
```

A draft includes:

```json
{
  "title": "Your balanced week",
  "content": {
    "summary": "...",
    "workouts": [],
    "meals": [],
    "adaptation_note": "...",
    "safety_note": "...",
    "estimated_weekly_cost": 0,
    "budget_currency": "USD"
  },
  "source": "llm",
  "requires_approval": true,
  "workflow_id": 1,
  "steps": [],
  "validation": {"valid": true, "checks": []}
}
```

This abbreviated illustration omits the actual nonempty workouts and agent steps. Each workout has `day`, `focus`, `duration_minutes`, and `exercises`; each exercise has `name`, `sets`, `reps`, and `rest_seconds`. Each meal has `name`, `why`, `cost`, `calories`, `protein_g`, `servings_per_week`, and `ingredients`. `cost` is per serving and `estimated_weekly_cost` totals exactly 21 servings for the week. Local menus use up to three compatible catalog recipes and can repeat the cheapest option to fit the budget. A menu that cannot meet the budget or dietary constraints is marked invalid and cannot be approved. These sample menu estimates are not a complete nutritional prescription.

After reviewing a returned draft, POST its `title`, `content`, `source`, and `workflow_id` to `/api/plans`. An unsatisfiable catalog/budget request can fail generation with HTTP 503. Any returned draft with `validation.valid = false` cannot be approved; approval returns HTTP 422. A failed validation leaves the active plan unchanged. Save-time validation uses the current profile, so changing preferences after generation can invalidate a draft. When a workflow ID is supplied, the submitted content must exactly match its recorded completed draft. Run history is available independently of active plans. Workflow execution is synchronous within the request; stored states are an audit trail, not a durable background queue. A process termination during execution can leave a run marked `running`.

## Workout journal

```bash
curl -X POST http://127.0.0.1:8000/api/workouts \
  -H 'Content-Type: application/json' \
  -d '{"exercise":"Strength training","duration_minutes":30,"perceived_effort":6,"notes":"Felt comfortable."}'
```

Duration is 1–300 minutes and effort is an integer from 1 to 10. The API assigns the completion timestamp.

## Pose summary and feedback

```bash
curl -X POST http://127.0.0.1:8000/api/pose-sessions \
  -H 'Content-Type: application/json' \
  -d '{"exercise":"Squat","duration_seconds":45,"reps":8,"analyzed_frames":650,"average_confidence":0.91,"range_of_motion":{"min":82,"max":171},"form_cues":["Keep the movement controlled."],"source":"webcam"}'
```

The response includes the saved session `id`. Request interpretation with:

```bash
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/agents/exercise_feedback/run \
  -H 'Content-Type: application/json' \
  -d '{"pose_session_id":1,"message":"Review my movement summary."}'
```

Optionally include `landmark_samples`: an array of at most eight numerical snapshots. Each snapshot has `time_seconds` and exactly 33 `landmarks`, each with finite `x`, `y`, `z`, and `visibility`. Coordinates allow `x`/`y` from −2 to 3 and `z` from −10 to 10; visibility is 0–1. Snapshot times must be chronological and within `duration_seconds`. Missing snapshots default to an empty array. These coordinates are measurements, not image/video data, and may be sent with context to a configured LLM.

Exercise names are `Squat`, `Bicep curl`, or `Arm circles`. Confidence is 0–1. The range minimum/maximum are degrees, constrained to 0–360, and the minimum cannot exceed the maximum. Session duration must be positive, analyzed frame count must be at least one, and source is `webcam` or `upload`. Repetition counts can be zero: a low-confidence or partial session can still be useful for feedback. These are client-derived estimates, not independently verified measurements.

## Coach chat

```bash
curl -X POST http://127.0.0.1:8000/api/assistant/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How should I adjust after a difficult week?","agent_id":"evaluation_adaptation"}'
```

`message` is required and limited to 1,200 characters. `agent_id` is optional. Chat responses include an answer and provenance; conversation history is persisted locally.

## Errors

Invalid typed request bodies return HTTP 422 with structured validation details. Unknown records or agent IDs return HTTP 404. A missing or unavailable model, malformed model output or exhausted constraint revision returns HTTP 503; the application does not substitute a local agent answer. If hard constraints cannot be satisfied, inspect the returned workflow validation/failure details before changing preferences or catalog data.
