# Deploy FitPilot on Vercel with Neon

The React frontend and MediaPipe assets are static files on Vercel's CDN. FastAPI runs as a Python function. Postgres is hosted in Neon. The existing SQLite mode remains available when DATABASE_URL is unset locally; Vercel requires DATABASE_URL and never falls back to temporary SQLite storage.

## Neon environment

Neon CLI writes `.env.local` (gitignored). Keep both strings server-only:

- `DATABASE_URL`: pooled URL for normal app requests.
- `DATABASE_URL_UNPOOLED`: direct URL for schema setup and data transfer.

Never prefix either name with `VITE_`. Never paste credentials into source files or chat. Vercel does not inherit local env files: add these variables through Vercel Project Settings → Environment Variables. Use the production branch for Production; a separate Neon branch for Preview/Development.

## Existing SQLite records

Before starting the API against an empty target, run from the repository root:

```sh
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python scripts/migrate_to_neon.py --sqlite database/fitpilot.db
```

The script reads `.env.local`, uses the direct URL, and copies the source read-only in one transaction. It preserves IDs and references, advances identity sequences, and refuses to overwrite any nonempty destination. Test on an isolated Neon branch first. A fresh installation can skip the transfer: API startup creates the schema and sample catalogs idempotently.

## Vercel settings

1. Import the GitHub repository and select the branch containing these changes.
2. Root directory: repository root (not `frontend`). Framework: FastAPI.
3. Keep the build command from `vercel.json`. It builds Vite and copies the complete output into root `public/` for CDN serving, including the pose model and matching WASM files.
4. Add both database URLs above. Leave `VITE_API_URL` unset: the frontend calls `/api` on the same domain.
5. Optional: add `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, and `LLM_TIMEOUT_SECONDS` if using a reachable model endpoint. Without one, coaching uses the existing labeled local rules. A localhost model URL on your computer is not reachable from Vercel.
6. Deploy. Open `/api/health` and confirm `database: connected`.

The app currently has one shared profile and no user authentication. Keep deployment access restricted for personal demos; separate user accounts and authorization are needed before offering private accounts to the public.

## Verify MediaPipe and persistence

- `/` shows the landing page; `/#/studio` opens the tracker.
- `/models/pose_landmarker_lite.task` returns the model, not HTML.
- `/mediapipe/wasm/vision_wasm_internal.wasm` returns WASM, not HTML.
- On HTTPS, allow the camera, keep the required joints visible, complete a movement and confirm the counter changes.
- Finish and save a session, reload the dashboard, and verify the record remains.
- Check the same record after a deployment: Neon persistence is independent of the function filesystem.

No camera footage is sent to Neon. The existing save action sends summary measurements and numerical landmark samples.

## Local development and tests

`python3 scripts/dev.py` loads root `.env.local`, root `.env`, then `backend/.env` without overriding already set environment values. Remove/unset DATABASE_URL to use local SQLite.

```sh
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -q
# Optional real Postgres tests: use a disposable local database, never production.
TEST_DATABASE_URL=postgresql://localhost/fitpilot_test PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -q
npm run build --prefix frontend
node --test frontend/src/pose/analysis.test.mjs
```

Postgres integration tests create and drop isolated `test_*` schemas. SQLite legacy migration has its own test; it is skipped in the Postgres subclass.

References: [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Neon Python](https://neon.com/docs/guides/python), [Neon connection pooling](https://neon.com/docs/connect/connection-pooling).
