from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import agents, db, tacc
from .schemas import ProfileUpdate, WorkoutLog, PlanSave, PoseSession, AgentRequest, ChatRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize()
    yield


app = FastAPI(title='FitPilot API', version='1.0.0', description='Coordinator, specialist agents, plans, pose summaries and progress persistence.', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()], allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Content-Type'])


def plan_row(row: Optional[dict]) -> Optional[dict]:
    if row:
        row['content'] = json.loads(row.pop('content_json'))
        row['source'] = row.pop('execution_source', None) or row['source']
    return row


def workflow_row(row: dict) -> dict:
    row['context'] = json.loads(row.pop('context_json'))
    row['result'] = json.loads(row.pop('result_json') or 'null')
    return row


@app.get('/api/health')
def health() -> dict[str, Any]:
    cfg = tacc.configuration()
    db.one('SELECT 1')
    return {'status': 'ok', 'database': 'connected', 'llm_configured': cfg['configured'], 'llm_status': 'configured_unverified' if cfg['configured'] else 'not_configured', 'model': cfg['model'], 'provider': cfg['provider'], 'timezone': os.getenv('FITPILOT_TIMEZONE', 'Asia/Hong_Kong')}


@app.get('/api/model/status')
def model_status() -> dict:
    cfg = tacc.configuration()
    if not cfg['configured']:
        return {'configured': False, 'reachable': False, 'model': cfg['model'], 'message': 'Set a valid LLM_BASE_URL or QWEN_BASE_URL to enable model requests.'}
    try:
        tacc.ask([{'role': 'user', 'content': 'Reply with OK.'}], max_tokens=8, timeout_override=8)
        return {'configured': True, 'reachable': True, 'model': cfg['model'], 'message': 'The configured model completed a test request.'}
    except tacc.ModelUnavailable as exc:
        return {'configured': True, 'reachable': False, 'model': cfg['model'], 'message': str(exc)}


@app.get('/api/profile')
def profile() -> dict:
    return agents.profile()


@app.put('/api/profile')
def update_profile(body: ProfileUpdate) -> dict:
    value = body.model_dump()
    value['scheduled_days'] = db.json_dump(value['scheduled_days'])
    fields = list(value)
    query = 'UPDATE profiles SET ' + ','.join(f'{field}=?' for field in fields) + ',updated_at=CURRENT_TIMESTAMP WHERE id=1'
    db.execute(query, tuple(value[field] for field in fields))
    return agents.profile()


@app.get('/api/overview')
def overview() -> dict:
    stats = db.one('SELECT COUNT(*) AS workouts,COALESCE(SUM(duration_minutes),0) AS minutes,COALESCE(AVG(perceived_effort),0) AS avg_effort FROM workout_logs WHERE completed_at>=?', (agents.week_start_utc(),))
    totals = db.one('SELECT COUNT(*) AS total_workouts,COALESCE(SUM(duration_minutes),0) AS total_minutes FROM workout_logs')
    stats.update(totals)
    stats['pose_sessions'] = db.one('SELECT COUNT(*) AS count FROM pose_sessions')['count']
    return {'profile': agents.profile(), 'stats': stats, 'recent_workouts': db.rows('SELECT * FROM workout_logs ORDER BY completed_at DESC,id DESC LIMIT 5'), 'active_plan': plan_row(db.one('SELECT * FROM plans WHERE is_active=1 ORDER BY id DESC LIMIT 1'))}


@app.get('/api/catalogs')
def catalogs() -> dict:
    return {'exercises': db.rows('SELECT * FROM exercises'), 'recipes': db.rows('SELECT * FROM recipes'), 'currency': 'USD', 'price_note': 'Sample per-serving estimates, not live market prices. HKD plans use a fixed 7.8 planning conversion.'}


@app.get('/api/plans')
def plans() -> list[dict]:
    return [plan_row(row) for row in db.rows('SELECT * FROM plans ORDER BY id DESC LIMIT 30')]


@app.post('/api/workflows/plan')
@app.post('/api/plans/generate')
def generate_plan() -> dict:
    return agents.workflow_plan()


@app.post('/api/plans')
def save_plan(body: PlanSave) -> dict:
    content = body.content.model_dump()
    validation = agents.validate_plan(content, agents.context())
    if not validation['valid']:
        raise HTTPException(422, {'message': 'The draft no longer meets your current preferences. Generate a new draft before approving.', 'validation': validation})
    if body.workflow_id is not None:
        workflow = db.one('SELECT result_json FROM workflows WHERE id=? AND status=?', (body.workflow_id, 'completed'))
        if not workflow:
            raise HTTPException(404, 'Completed workflow not found')
        result = json.loads(workflow['result_json'])
        if result['content'] != content:
            raise HTTPException(422, 'The submitted plan does not match the recorded workflow draft')
        source = result['source']
    else:
        source = 'local_fallback'
    with db.connect() as conn:
        # Activation is atomic: a rejected draft cannot deactivate the existing plan.
        conn.execute('UPDATE plans SET is_active=0 WHERE is_active=1')
        plan_id = db.insert_id(conn, 'INSERT INTO plans(title,content_json,source,is_active,workflow_id,execution_source) VALUES(?,?,?,1,?,?)', (body.title, db.json_dump(content), 'tacc_qwen' if source in ['llm', 'tacc_qwen'] else 'local_fallback', body.workflow_id, source))
    result = plan_row(db.one('SELECT * FROM plans WHERE id=?', (plan_id,)))
    result['validation'] = validation
    return result


@app.get('/api/workflows')
def workflows(limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    return [workflow_row(row) for row in db.rows('SELECT * FROM workflows ORDER BY id DESC LIMIT ?', (limit,))]


@app.get('/api/workflows/{workflow_id}')
def workflow(workflow_id: int) -> dict:
    row = db.one('SELECT * FROM workflows WHERE id=?', (workflow_id,))
    if not row:
        raise HTTPException(404, 'Workflow not found')
    result = workflow_row(row)
    result['steps'] = [agents.run_row(row) for row in db.rows('SELECT * FROM agent_runs WHERE workflow_id=? ORDER BY id', (workflow_id,))]
    return result


@app.get('/api/agents')
def agent_catalog() -> dict:
    return {'coordinator': {'name': 'Central Coordinator', 'description': 'Routes requests, shares context, invokes specialists and validates drafts before approval.'}, 'agents': agents.AGENTS}


@app.get('/api/agent-runs')
def agent_runs(limit: int = Query(default=30, ge=1, le=100), agent_id: Optional[str] = None) -> list[dict]:
    rows = db.rows('SELECT * FROM agent_runs WHERE agent_id=? ORDER BY id DESC LIMIT ?', (agent_id, limit)) if agent_id else db.rows('SELECT * FROM agent_runs ORDER BY id DESC LIMIT ?', (limit,))
    return [agents.run_row(row) for row in rows]


@app.post('/api/agents/{agent_id}/run')
def run_agent(agent_id: str, body: AgentRequest) -> dict:
    if agent_id not in agents.MODELS:
        raise HTTPException(404, 'Unknown agent')
    if body.pose_session_id and not db.one('SELECT id FROM pose_sessions WHERE id=?', (body.pose_session_id,)):
        raise HTTPException(404, 'Pose session not found')
    return agents.run_agent(agent_id, agents.context(body.pose_session_id), body.message)


@app.post('/api/pose-sessions')
def save_pose(body: PoseSession) -> dict:
    value = body.model_dump()
    row_id = db.execute('INSERT INTO pose_sessions(exercise,summary_json) VALUES(?,?)', (value['exercise'], db.json_dump(value)))
    return agents.pose_row(db.one('SELECT * FROM pose_sessions WHERE id=?', (row_id,)))


@app.get('/api/pose-sessions')
def pose_sessions(limit: int = Query(default=30, ge=1, le=100)) -> list[dict]:
    return [agents.pose_row(row) for row in db.rows('SELECT * FROM pose_sessions ORDER BY id DESC LIMIT ?', (limit,))]


@app.get('/api/workouts')
def workouts(limit: int = Query(default=50, ge=1, le=1000)) -> list[dict]:
    return db.rows('SELECT * FROM workout_logs ORDER BY completed_at DESC,id DESC LIMIT ?', (limit,))


@app.post('/api/workouts')
def log_workout(body: WorkoutLog) -> dict:
    value = body.model_dump()
    row_id = db.execute('INSERT INTO workout_logs(exercise,duration_minutes,perceived_effort,notes) VALUES(?,?,?,?)', (value['exercise'], value['duration_minutes'], value['perceived_effort'], value['notes']))
    return db.one('SELECT * FROM workout_logs WHERE id=?', (row_id,))


@app.get('/api/assistant/messages')
def chat_messages() -> list[dict]:
    return db.rows('SELECT * FROM (SELECT * FROM chat_messages ORDER BY id DESC LIMIT 100) AS recent_messages ORDER BY id')


def route_message(message: str) -> str:
    text = message.lower()
    if any(word in text for word in ['meal', 'food', 'diet', 'nutrition', 'protein', 'budget', 'eat']):
        return 'nutrition'
    if any(word in text for word in ['pose', 'form', 'rep', 'camera', 'curl', 'squat']):
        return 'exercise_feedback'
    if any(word in text for word in ['progress', 'adapt', 'evaluate', 'effort', 'replan']):
        return 'evaluation_adaptation'
    if any(word in text for word in ['workout', 'exercise', 'schedule', 'train']):
        return 'exercise_planning'
    return 'goal_planning'


@app.post('/api/assistant/chat')
def assistant_chat(body: ChatRequest) -> dict:
    agent_id = body.agent_id or route_message(body.message)
    if agent_id not in agents.MODELS:
        raise HTTPException(404, 'Unknown agent')
    db.execute('INSERT INTO chat_messages(role,text) VALUES(?,?)', ('user', body.message))
    run = agents.run_agent(agent_id, agents.context(), body.message)
    output = run['output']
    pieces = [output['summary']]
    for key in ['priorities', 'suggestions', 'recommendations', 'notes']:
        if output.get(key):
            pieces.extend(output[key][:3])
    answer = '\n\n'.join(pieces)
    db.execute('INSERT INTO chat_messages(role,text,source,agent_run_id) VALUES(?,?,?,?)', ('assistant', answer, run['source'], run['id']))
    return {'answer': answer, 'source': run['source'], 'agent_id': agent_id, 'run_id': run['id']}


# When built, the same server can host the SPA. Register API/docs routes first.
FRONTEND_DIST = db.ROOT / 'frontend' / 'dist'
if (FRONTEND_DIST / 'index.html').is_file():
    if (FRONTEND_DIST / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=FRONTEND_DIST / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path.startswith('api/') or path == 'api':
            raise HTTPException(404, 'API route not found')
        candidate = (FRONTEND_DIST / path).resolve()
        if candidate.is_relative_to(FRONTEND_DIST.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / 'index.html')
