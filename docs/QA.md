# Verification and manual checks

## Automated checks

Run these commands from the project root after installing dependencies:

```bash
(cd backend && .venv/bin/python -m unittest discover -s tests -v)
(cd frontend && npm run build)
```

Backend tests use an isolated temporary database rather than the development profile or workout journal. The frontend production build includes TypeScript checking. Pure pose analysis tests additionally require Node.js 22.18+ and can be run with `node --test frontend/src/pose/analysis.test.mjs`; see [POSE.md](POSE.md).

## Manual walkthrough

1. Start the API and UI with `python3 scripts/dev.py`. Open the UI at `http://127.0.0.1:5173` and API documentation at `http://127.0.0.1:8000/docs`.
2. Open preferences. Save a name, goal, experience, number of workout days, session duration, equipment, schedule, food preferences/allergies, limitations, and meal budget. Reload and confirm the saved values remain.
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

## Model configuration checks

With no LLM URL set, run planning and the individual agents; results should identify local execution. With a reachable compatible endpoint, confirm at least one successful result identifies live inference. Point the backend at an unreachable endpoint and confirm fallback/error details remain visible.

Use a mock compatible endpoint for repeatable tests of malformed JSON, HTTP failures, and invalid constraints. A model's natural-language assertion that a plan is safe is not a substitute for application validation.

## Real-world verification limits

Unit tests and a successful build cannot prove webcam permission behavior, rep accuracy on a particular person, GPU compatibility, or model availability on a TACC node. Test those on the intended browser, device, camera position, and course network. Uploaded clips may need conversion to a codec supported by the browser.

## Course evaluation still to perform

The original proposal defines a research evaluation beyond ordinary implementation checks: 15 labeled exercise clips, 20 planning requests with varied constraints, 10 multi-step adaptation scenarios, and comparisons with single-call and single-agent baselines. Those datasets and comparative measurements are not supplied by this repository's implementation tests. Collect and report them separately before claiming accuracy, recommendation-quality gains, or inference-cost improvements.
