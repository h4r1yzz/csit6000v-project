# Clean verification for the FitPilot grading revision

**Source commit** `ca94084617e3458ce639b7074debfe9029af3eb9` ([pinned source](https://github.com/h4r1yzz/csit6000v-project/tree/grading-submission-2026-11-21-v4)). The evidence was generated outside a fresh checkout of that commit. `git status --porcelain` was empty before and after the checks. See [source and environment details](source.txt).

## Local verification

The frontend build, 43 backend tests, 17 pose unit tests, and simulated end-to-end API smoke test passed. The chat demo restored four messages after login and found three stored model requests. The case validator accepted all 20 planning and 10 adaptation inputs. The table builder regenerated the original Tables 1–5 byte for byte.

- [Verification record](verification.json) and [backend test log](backend_tests.log)
- [Pose tests](pose_tests.log), [frontend build](frontend_build.log), and [API smoke test](api_smoke.log)
- [Chat persistence](demo-chat.log) and [case-bank validation](validate-cases.log)

## Replay of all 270 original trials

The [replay script](replay_archived.py) supplies the archived model replies at the transport boundary and reruns the current coordinator, validation, and scoring against a fresh PostgreSQL database. Each trial compares the regenerated model request bodies, normalized output, validation results, score, model calls, and recorded specialist flow. The [replay record](replay-original.json) lists zero differences across all 180 planning and 90 adaptation attempts. Replay reproduces the score and workflow behavior for those archived responses. The original timings were measured during the live runs.

To reproduce, set `TEST_DATABASE_URL` to a disposable PostgreSQL database as in the project README. From the pinned source checkout, run the published script using the environment created during setup. The following assumes the evidence was downloaded to `../evidence`.

```bash
backend/.venv/bin/python ../evidence/replay_archived.py --source .
```

## Fresh live checks

The [live smoke test](live-smoke.log) used the course TACC `qwen3.8-27b` service. All five stages returned with live model provenance and the approved plan was read back from PostgreSQL. The [live run manifest](live-run.json) records the source SHA, the arguments, and the exit code of each command.

The confirmation set covers P02 (two scheduled workout days), P04 (10-minute cap), and P19 (zero budget) for planning, plus A04 (schedule change), A05 (vegan meals), and A09 (zero budget after a plan) for adaptation. Each of the three methods runs each case three times using four workers. The selected cases exercise a normal plan, the earlier time-limit failure mode, a dietary replan, and explicit menu rejection. This smaller live run checks representative cases. The replay above covers the complete original evaluation.

Use the [live setup instructions](https://github.com/h4r1yzz/csit6000v-project/blob/grading-submission-2026-11-21-v4/README.md#rerun-the-live-evaluation) to configure the service. Add `--case-ids P02 P04 P19` to the planning command and `--case-ids A04 A05 A09` to the adaptation command to reproduce this confirmation set. Choose fresh output paths. Model replies and timings can vary between runs.

### Observed confirmation results

| Mode | Planning feasible passes | Planning infeasible rejections | Adaptation feasible passes | Adaptation infeasible rejections |
| --- | ---: | ---: | ---: | ---: |
| Five specialists | 4/6 | 3/3 | 6/6 | 3/3 |
| One call | 0/6 | 0/3 | 0/6 | 0/3 |
| Generalist plus revision | 0/6 | 0/3 | 0/6 | 0/3 |

Both planning misses for the specialist workflow were P04 `session_time` failures after revision. Those misses are included in the denominator. These rates describe the selected cases. See the [planning traces](planning-confirmation.json), [adaptation traces](adaptation-confirmation.json), and [timing, usage, outcomes, and stage tables](confirmation-tables.md). The [live feedback run](live-feedback.json) passed all three synthetic measurement checks.
