# Verify the grading revision

Clone the [pinned grading source](https://github.com/h4r1yzz/csit6000v-project/tree/grading-submission-2026-11-21-v4) using the [README setup](../README.md#getting-started-instructions). The [clean run evidence](https://github.com/h4r1yzz/csit6000v-project/tree/grading-evidence-2026-11-21-v4/evaluation/clean-v4) contains the executed commit, tool versions, verification logs, and live run records. Evidence has a separate tag because adding generated files changes the source commit SHA. The recorded SHA can be compared with the grading tag's commit.

## Verify your checkout and run

From the pinned clone root, record the source identity and write new results to a directory outside the clone.

```bash
git rev-parse HEAD
git rev-parse 'grading-submission-2026-11-21-v4^{commit}'
git status --porcelain
RUN_DIR=$(mktemp -d)
backend/.venv/bin/python scripts/verify.py --output "$RUN_DIR/verification.json"
```

The SHAs should match and `git status --porcelain` should print nothing. `verification.json` records the exact commit and the working tree status at launch. The verification builds the frontend, runs all backend and pose tests, and exercises account registration, planning, approval, and readback with simulated model replies.

With a reachable model and the configuration in [Rerun the live evaluation](../README.md#rerun-the-live-evaluation), run the live end-to-end example on a disposable test database.

```bash
backend/.venv/bin/python scripts/smoke.py --live
```

A passing run prints `PASS: account -> five live model stages -> valid draft -> approval -> persisted active plan` and the configured model and provider. The live path uses Tuesday and Saturday workout sessions, the same schedule tested by planning case P02. It checks the order and provenance of all five stages and confirms that no draft becomes active until approval.

## Read the original and clean records

[Tables 1–5](EVALUATION.md#recorded-live-results) describe the original 270 planning and adaptation trials. Their JSON metadata preserves the original base commit, dirty-tree flag, and evaluator hashes. The same case banks and validator apply to the clean run. Its evidence reports which cases and repeats were executed and how they scored. Treat differences as independent model outcomes under the documented configuration.

The original specialist, revision, and adaptation recordings contain a SHA-256 matching the submitted `scripts/evaluate.py`. The original one-call planning records contain the earlier runner hash. The `working_tree_modified` flag covers the entire working tree, so the original metadata alone cannot establish a clean checkout. Use the clean run logs and exact source commit for that check.
