# Recorded verification

Recorded for this implementation on 2026-11-13 (Asia/Hong_Kong). This report distinguishes completed automated checks from device, browser, and external-service checks that remain unverified.

## Completed checks

| Command/check | Result |
| --- | --- |
| `cd frontend && npm run build` | Passed TypeScript checking and Vite production build. |
| `cd backend && .venv/bin/python -m unittest discover -s tests -v` | 21 tests passed, zero skipped, with the production frontend build present. Tests use temporary isolated databases. |
| `node --test frontend/src/pose/analysis.test.mjs` | Nine pose analysis tests passed. |
| `git diff --check` | Passed whitespace/error checks. |
| `FITPILOT_DB_PATH=/tmp/fitpilot-supervisor-qa-20261113.db python3 scripts/dev.py` | Both Uvicorn and Vite reached ready state using an isolated database. Ctrl+C exited with status 0 and stopped the owned processes; a subsequent port check found no listeners on 8000/5173. |
| Component render smoke using Vite `ssrLoadModule`, React, and `react-dom/server.renderToString` | Passed rendering of current plan approval/meals/validation/provenance, a legacy plan with the original meal shape, preference fields/weekday picker, and nested agent output arrays/booleans. This was a server render check, not browser UI verification. |
| Compile `scripts/dev.py` with Python's `compile(...)` | Passed syntax validation. |
| Resolve repository-relative links in README and `docs/*.md` | Passed local documentation link validation. |

Backend coverage includes typed API validation, schedule/time/catalog/diet/budget checks, atomic plan approval and stale-draft rejection, saved workflows/history, pose summary and landmark validation, agent feedback/adaptation, fallback behavior, and the OpenAI-compatible transport using a local mock HTTP service. Transport checks verify the request path, model, bearer authorization, and Qwen-specific options. A mock service does not prove availability of the real TACC endpoint.

The legacy migration test starts from a fixture of the original schema, initializes the current schema twice, and verifies that existing profile data, workout records, plan JSON, plan sources/active flags, and a custom recipe survive. It also checks additive defaults and the availability of new agent/pose tables. The built-frontend route test uses FastAPI TestClient to verify index, JavaScript/CSS assets, docs, and OpenAPI responses, plus 404 handling for an unknown API route. These HTTP checks do not execute browser JavaScript.

Pose tests cover angle geometry, full and partial repetitions, confidence gating, visible-side selection, tracking gaps, circle counting, numerical snapshot bounds, and snapshot sampling. These tests exercise the pure state machine with synthetic landmark inputs; they do not run the MediaPipe model on real video.

The original development database was not used for automated test writes or reset. Existing user files and local database records were retained. This task did not publish a hosted website.

## Verification limits

Browser automation could not open the local preview because the browser permission gate rejected the local origin. Consequently, no successful visual inspection, browser interaction pass, live camera permission test, hardware MediaPipe inference, or real-clip accuracy check is claimed. Successful process startup, TestClient HTTP checks, and component server rendering do not replace those browser checks.

The local dashboard needs a route from FastAPI to the model service for interactive inference. A valid model URL in `/api/health` reports configuration only. Use `/api/model/status` and inspect each result's source after configuring the intended service. The SSH forwarding route tested below provides that connection on the configured TACC account.

The course proposal's labeled video evaluation and baseline comparisons remain separate work. See [QA.md](QA.md) for manual checks and the proposed evaluation matrix. No clinical or rep-accuracy benchmark is implied by the automated results above.

## TACC batch verification on 2026-11-14

GPU job `29026` served `qwen3.8-27b`. CPU job `29032` ran the FitPilot coordinator against that service with the seeded demo profile. The downloaded result reported `succeeded`, five `tacc_qwen` stages, and seven passing plan checks. The resulting draft included four workouts and 21 meal servings and took 47.266 seconds to generate.

The course runtime could reach the service at its private IPv4 address. The laptop could neither resolve the compute hostname nor reach the private address, so live inference was verified through the CPU job. The batch uses UTC to run in the course runtime without IANA timezone data. See the [TACC setup guide](../backend/tacc/README.md) to reproduce the run.

The backend suite passed 23 tests after adding the batch client. The batch tests verify the staged files, HTTP request format, sources, schedule assignment, and preservation of the result on fallback. The supplied job scripts also passed Bash syntax checks.

## Local app with TACC inference on 2026-11-14

GPU job `29070` served Qwen. `scripts/dev.py --tacc-job` connected to it through the SDK's configured SSH gateway and bound the forwarding port to `127.0.0.1`. Vite and FastAPI ran on the Mac. The dashboard returned HTTP 200, and `/api/model/status` through the local Vite proxy returned `reachable: true` for `qwen3.8-27b`.

The local FastAPI plan workflow, tested with a temporary SQLite database, used `tacc_qwen` for all five stages and passed all seven plan checks. The backend suite and browser pose analyzer suite passed 23 and nine tests respectively. This check exercised live inference from the local backend without requiring a TACC CPU job or sending webcam video.
