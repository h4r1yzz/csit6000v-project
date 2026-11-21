# Reviewer walkthrough: test cases and conversations

Open [the evaluation report](EVALUATION.md) for the scoring rules and Tables 1–5. This walkthrough connects those results to individual test inputs, agent outputs, and failure traces. All examples use synthetic data.

## Test cases and expected behavior

The complete inputs and expected outcomes are in the [20 planning cases](../evaluation/planning_cases.json) and [10 adaptation cases](../evaluation/adaptation_cases.json). Planning covers schedule, session length, equipment, experience, diet, allergies, currency, and incompatible constraints. Adaptation applies profile changes to a known valid starting plan. The [three feedback cases](../evaluation/results/feedback.json) cover missing, low-confidence, and clear measurements.

| Case | What the app receives | What the reviewer should check |
| --- | --- | --- |
| P02 | Two workout days, Tuesday and Saturday | The draft has exactly those two sessions. Each stage completes and the draft passes all seven checks. |
| P04 | A 10-minute session cap | The workout fits the work, rests, and warm-up within the cap. An invalid exercise draft receives one revision. A second failure stops the workflow. |
| P19 | A weekly meal budget of USD 0 | The workflow explains the menu conflict and stops at nutrition. |
| A05 | A change to vegan meals after a prior plan | The old menu fails the new preference. The new draft passes validation with catalog meals matching the vegan preference. |
| Low-visibility feedback | Four synthetic squat reps, confidence 0.43 | The response preserves the measurements and displays a low-visibility warning. |

## Live TACC Qwen examples

The examples below identify a case, method, and repeat so graders can check them against the [planning traces](../evaluation/results/planning.json), [adaptation traces](../evaluation/results/adaptation.json), and [feedback record](../evaluation/results/feedback.json). The planning inputs are saved profile settings. The agent text in quotes comes from the recorded outputs.

### P02, repeat 1: A complete five-agent plan

The user selects Tuesday and Saturday. The rest of the synthetic profile allows 35 minutes per session, bodyweight and dumbbell exercises, and USD 70 per week for meals.

| Stage | Recorded output excerpt |
| --- | --- |
| Goal Planning | “The plan accommodates a 2-day weekly schedule (Tuesday and Saturday) with 35-minute sessions using bodyweight and dumbbells.” |
| Exercise Planning | The schedule contains Tuesday and Saturday sessions, both 35 minutes long. |
| Nutrition | The selected menu contains seven servings each of lentil tomato soup, egg and avocado toast, and Greek yogurt berry bowl. Total cost is USD 59.50. |
| Exercise Feedback | “No measurements available.” The returned measurement fields are empty. |
| Evaluation and Adaptation | “No recent activity or session data is available to evaluate adherence or effort.” The final structured draft passed all seven checks. |

All five stages completed in order. The trial took 61.5 seconds, five model calls, and 13,663 total tokens. The one-call baseline on the same case and repeat said `NO_COMPATIBLE_MENU` and returned no meals. The validator recorded failures for dietary compatibility and weekly servings, and the scorer counted it as a miss for a feasible profile.

### P19 and P04: Two reasons for stopping early

- **P19, repeat 1.** With a zero meal budget, Goal Planning and Exercise Planning completed. The catalog check stopped Nutrition before its model call and returned “No menu meets the recorded dietary and budget constraints.” This counted as a correct rejection.
- **P04, repeat 2.** With a 10-minute cap, Exercise Planning failed `session_time`. The next request included `revision_required: Deterministic checks failed: session_time`. The revision also failed the same check, so the workflow ended before Nutrition. This counted as a failed feasible trial.

### A05, repeat 1: A valid draft with an error in the explanation

After the user switched to vegan meals, the starting plan failed the updated constraint check. The new draft selected seven servings each of oat banana bowl, chickpea rice bowl, and lentil tomato soup for USD 41.30, and passed all seven checks. The Nutrition summary gave approximately **497 g** of weekly protein. The selected catalog values total **385 g** (7 × (12 + 19 + 24)). This example shows why a passing structured plan score does not establish the accuracy of every sentence in the model's explanation. The example is a spot check and does not estimate a prose error rate.

### Exercise feedback: Two interpretations of the same measured angles

The signed-in request sends a synthetic squat summary with 4 reps, 145 analyzed frames, 15 seconds, and average confidence 0.43. The live agent endpoint returned HTTP 200 and preserved the metrics. The app adds the confidence note “Low visibility: these measurements are unreliable. Reposition the camera before using the feedback.”

The model's low-confidence response called the 79°–171° range “shallow.” The clear-view case supplied the same angles with confidence 0.91, and its response described “a deep squat depth.” Both passed the automated check, which requires a low-visibility warning in the low-confidence case. The examples use summary values supplied by the fixture, so a correct form interpretation cannot be established from these trials.

## Coach conversation and persistence demo

This example uses the signed-in `/api/assistant/chat` route with a simulated model. The profile tool, request logging, login, and PostgreSQL readback all run through the app. With a disposable `TEST_DATABASE_URL` set as described in the [README](../README.md#getting-started-instructions), run:

```bash
backend/.venv/bin/python scripts/demo_chat.py
```

```text
SIMULATED MODEL: FitPilot API, tools, and Postgres are exercised.
User: What goal did I save?
FitPilot: Your saved goal is: Train for a walking holiday.
User: How many minutes did I set for each session?
FitPilot: You set 20 minutes per session.
PASS: get_profile succeeded; 4 chat messages restored after login; 3 model requests recorded.
```

The first turn calls `get_profile` and receives its result before answering. The follow-up request receives the saved profile and the earlier question. The demo signs out, confirms the history endpoint requires authentication, signs back in, and reads all four messages through `GET /api/assistant/messages`. It uses temporary database schemas and removes them on exit.

## Where conversations and agent records are stored

| Record | Storage and access |
| --- | --- |
| Coach messages | `chat_messages` in the signed-in account's PostgreSQL schema. The dashboard uses `GET /api/assistant/messages` to load the latest 100 messages. |
| Agent inputs and outputs | `agent_runs` and `workflows` in the same account schema. Read them through the signed-in agent-runs and workflow endpoints. |
| Model prompts | `model_prompts` stores the prepared model request, including messages and tool context when present, plus model name, status, and optional agent-run ID. Transport credentials are excluded. The table is available to the database operator, since the app exposes no prompt history route. |
| Public evaluation examples | The committed trace files under [`evaluation/results`](../evaluation/results) contain synthetic inputs and evaluation responses. They are suitable for grader review without an account on the running FitPilot app. |

The coach uses the saved profile and up to six recent user questions as context. The chat history shown in the UI includes prior assistant replies, while the next model request uses the recent questions. See the [database guide](DATABASE.md) and [API reference](API.md).
