# Reproduce the FitPilot grading results

The [final grading package](https://github.com/h4r1yzz/csit6000v-project/tree/grading-final) includes the app, evaluation inputs, instructions, and evidence. The evaluated source is [`ca94084617e3458ce639b7074debfe9029af3eb9`](https://github.com/h4r1yzz/csit6000v-project/tree/ca94084617e3458ce639b7074debfe9029af3eb9), also tagged `grading-submission-2026-11-21-v4`. The grading package includes later dashboard changes, the submission PDF, and a PostgreSQL Compose option. The backend workflow, case banks, and evaluation scripts match v4.

From a Git checkout containing both tags, compare the evaluated backend and experiment inputs. Expect no diff.

```bash
git diff --exit-code grading-submission-2026-11-21-v4 grading-final \
  -- backend/app backend/tacc/serve backend/requirements.txt backend/requirements-dev.txt \
  database evaluation/planning_cases.json evaluation/adaptation_cases.json \
  scripts/dev.py scripts/tacc_connection.py scripts/verify.py scripts/smoke.py \
  scripts/evaluate.py scripts/evaluate_feedback.py scripts/summarize_evaluation.py
```

## Run from the exact evaluated source

```bash
git clone --branch grading-submission-2026-11-21-v4 \
  https://github.com/h4r1yzz/csit6000v-project.git fitpilot-v4
cd fitpilot-v4
git rev-parse HEAD
git status --porcelain
```

Expect `ca94084617e3458ce639b7074debfe9029af3eb9` and no status output. Install the dependencies and configure a disposable PostgreSQL database as described in [Getting Started](../README.md#getting-started-instructions). If you use the Compose database, start it from the final package and export that database URL in the v4 clone's shell. Write new logs and JSON outside the v4 clone.

```bash
RUN_DIR=$(mktemp -d)
backend/.venv/bin/python scripts/verify.py --output "$RUN_DIR/verification.json"
```

The [new verification record](../evaluation/full-v4/verification.json) records the exact commit and clean tree. The [app launch log](../evaluation/full-v4/app-launch.log) checks that Vite serves the dashboard and FastAPI can reach PostgreSQL. With a reachable Qwen endpoint configured as in the README, `backend/.venv/bin/python scripts/smoke.py --live` checks all five live agent stages, approval, and plan readback through the signed-in API.

## Compare the evaluation records

| Evidence | What it shows |
| --- | --- |
| [Original 270 trials](EVALUATION.md#recorded-live-results) | Initial live measurements, methodology, and Tables 1–5. Original metadata preserves the checkout's dirty-tree flag. |
| [Clean replay of archived traces](../evaluation/clean-v4) | Replays the original responses against clean v4. All 270 model request bodies, scoring outcomes, and recorded flows matched. |
| [Fresh full evaluation](../evaluation/full-v4) | Runs all 180 planning and 90 adaptation trials again with live TACC Qwen from clean v4. Includes feedback, raw traces, logs, regenerated tables, and environment provenance. |

To regenerate the fresh tables from the final package, use this command from the package root. It reads the archived JSON and needs only Python.

```bash
python3.11 scripts/summarize_evaluation.py \
  --planning evaluation/full-v4/planning.json \
  --adaptation evaluation/full-v4/adaptation.json
```

The generated Markdown should match [the fresh Tables 1–5](../evaluation/full-v4/tables.md). To generate new live trials use the [live commands in the README](../README.md#rerun-the-live-evaluation). Compare feasible pass rates, explicit rejections, stage completion, and latency spread. The cases are synthetic, and model wording, timing, and per-case outcomes can vary.

If the serving job is close to its time limit, stop the evaluator after its latest checkpoint and connect to the replacement service. Keep the same case bank, repeat count, worker count, model name, and output path. For example, resume adaptation with the original `RUN_DIR` still set.

```bash
backend/.venv/bin/python scripts/evaluate.py --suite adaptation \
  --repeats 3 --workers 4 --output "$RUN_DIR/adaptation.json" --resume
```
