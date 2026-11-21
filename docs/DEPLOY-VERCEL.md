# Deploy FitPilot on Vercel with Neon

The React frontend and MediaPipe assets are static files on Vercel's CDN. FastAPI runs as a Python function. Postgres is hosted in Neon. Local development also requires `DATABASE_URL` (there is no SQLite mode).

## Neon environment

Neon CLI writes `.env.local` (gitignored). Keep both strings server-only:

- `DATABASE_URL`: pooled URL for normal app requests.
- `DATABASE_URL_UNPOOLED`: direct URL for schema setup.

Never prefix either name with `VITE_`. Never paste credentials into source files or chat. Vercel does not inherit local env files: add these variables through Vercel Project Settings → Environment Variables. Use the production branch for Production; a separate Neon branch for Preview/Development.

## Neon schema

Apply `database/schema.postgres.sql` and `database/auth.sql` on a fresh Neon database (or Neon SQL Editor) before the first API traffic. Local `scripts/dev.py` initializes schema automatically when `DATABASE_URL` is set. Schema changes after go-live should be applied explicitly on Neon before deploying code that needs them.

The app role needs permission to create schemas for newly registered accounts. Browser accounts use separate Postgres schemas (`fitpilot_account_<id>`).

## Vercel settings

1. Import the GitHub repository and select the branch containing these changes.
2. Root directory: repository root (not `frontend`). Framework: FastAPI.
3. Keep the build command from `vercel.json`. It builds Vite and copies the complete output into root `public/` for CDN serving, including the pose model and matching WASM files.
4. Add both database URLs above. Leave `VITE_API_URL` unset: the frontend calls `/api` on the same domain.
5. For planning and coaching, add `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` (if required), and `LLM_TIMEOUT_SECONDS` for a reachable model endpoint. Without one, model-dependent requests return HTTP 503. A localhost model URL on your computer is not reachable from Vercel.
6. Deploy. Open `/api/health` and confirm `database: connected`.

## Verify MediaPipe and persistence

- `/` shows the landing page; `/#/studio` opens the tracker.
- `/models/pose_landmarker_lite.task` returns the model, not HTML.
- `/mediapipe/wasm/vision_wasm_internal.wasm` returns WASM, not HTML.
- On HTTPS, allow the camera, keep the required joints visible, complete a movement and confirm the counter changes.
- Finish and save a session, reload the dashboard, and verify the record remains.
- Check the same record after a deployment: Neon persistence is independent of the function filesystem.

No camera footage is sent to Neon. The existing save action sends summary measurements and numerical landmark samples.

## Local development and tests

`python3 scripts/dev.py` loads root `.env.local`, root `.env`, then `backend/.env` without overriding already set environment values. `DATABASE_URL` is required.

```sh
# Prefer TEST_DATABASE_URL pointing at a disposable Neon branch.
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -q
npm run build --prefix frontend
node --test frontend/src/pose/analysis.test.mjs
```

Unit tests and smoke create and drop isolated `test_*` schemas.

References: [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Neon Python](https://neon.com/docs/guides/python), [Neon connection pooling](https://neon.com/docs/connect/connection-pooling).

## Database startup

Vercel cold starts do not create the Neon schema. Provision Postgres with the SQL files above before the first deployment. Local development initializes its database automatically when `DATABASE_URL` is set.
