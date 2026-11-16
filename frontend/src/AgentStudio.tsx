import { useCallback, useEffect, useState } from 'react'
import { ArrowDown, ArrowRight, Check, CheckCircle2, Clock3, GitBranch, LoaderCircle, Play, RefreshCw, Sparkles, XCircle } from 'lucide-react'
import { api } from './api'
import type { Agent, AgentRun, PoseSession } from './types'

export function sourceLabel(source: string) {
  if (source === 'local_fallback' || source === 'offline' || source === 'local') return 'Local rules'
  if (source === 'mixed') return 'LLM + local rules'
  if (source === 'tacc_qwen') return 'TACC Qwen'
  if (source === 'llm') return 'LLM'
  return source.replace(/_/g, ' ')
}

export function label(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase())
}

function ResultValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value == null) return <span className="result-muted">No data yet</span>
  if (typeof value === 'boolean') return <span className={value ? 'result-pass' : 'result-muted'}>{value ? 'Yes' : 'No'}</span>
  if (typeof value === 'string' || typeof value === 'number') return <span className="result-text">{String(value)}</span>
  if (Array.isArray(value)) return value.length ? <ul className="result-list">{value.map((item, i) => <li key={i}><ResultValue value={item} depth={depth + 1}/></li>)}</ul> : <span className="result-muted">None</span>
  if (depth > 6) return <span className="result-text">{JSON.stringify(value)}</span>
  return <dl className="result-fields">{Object.entries(value as Record<string, unknown>).map(([key, item]) => <div key={key}><dt>{label(key)}</dt><dd><ResultValue value={item} depth={depth + 1}/></dd></div>)}</dl>
}

export function RunDetails({ run }: { run: AgentRun }) {
  return <div className="run-details">
    <div className="run-meta"><span className="source-tag">{sourceLabel(run.source)}</span><span>Run #{run.id}</span><span>{run.status}</span></div>
    {run.error && <p className="inline-error">{run.error}</p>}
    <ResultValue value={run.output}/>
  </div>
}

export function WorkflowTrace({ runs }: { runs: AgentRun[] }) {
  return <div className="workflow-trace">{runs.map(run => <details key={run.id} className="trace-step"><summary><span className="trace-status">{run.status === 'completed' ? <CheckCircle2 size={16}/> : <XCircle size={16}/>}</span><strong>{label(run.agent_id)}</strong><span className="source-tag">{sourceLabel(run.source)}</span></summary><RunDetails run={run}/></details>)}</div>
}

export default function AgentStudio({ onGenerate, generating, configured, revision }: { onGenerate: () => void; generating: boolean; configured: boolean; revision: number }) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [sessions, setSessions] = useState<PoseSession[]>([])
  const [selected, setSelected] = useState('goal_planning')
  const [message, setMessage] = useState('')
  const [poseId, setPoseId] = useState('')
  const [result, setResult] = useState<AgentRun | null>(null)
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modelStatus, setModelStatus] = useState('')
  const [checking, setChecking] = useState(false)

  const load = useCallback(async () => {
    try {
      const [catalog, history, pose] = await Promise.all([api.get<{ agents: Agent[] }>('/api/agents'), api.get<AgentRun[]>('/api/agent-runs'), api.get<PoseSession[]>('/api/pose-sessions')])
      setAgents(catalog.agents); setRuns(history); setSessions(pose); setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load agents') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load, revision])

  async function runAgent(e: React.FormEvent) {
    e.preventDefault(); setRunning(true); setError(''); setResult(null)
    try {
      const run = await api.post<AgentRun>(`/api/agents/${selected}/run`, { message, ...(poseId && selected === 'exercise_feedback' ? { pose_session_id: Number(poseId) } : {}) })
      setResult(run); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Agent could not complete the run') }
    finally { setRunning(false) }
  }
  async function checkModel() {
    setChecking(true)
    try {
      const status = await api.get<{ reachable?: boolean; connected?: boolean; status?: string; detail?: string; message?: string }>('/api/model/status')
      setModelStatus(status.message || status.detail || ((status.reachable || status.connected || status.status === 'connected') ? 'Connection successful' : 'Model unavailable. Local rules remain available.'))
    } catch (e) { setModelStatus(e instanceof Error ? e.message : 'Connection failed') }
    finally { setChecking(false) }
  }
  return <div className="page-content subpage coaching-page">
    <section className="subpage-heading"><div><div className="date-eyebrow"><GitBranch size={15}/>YOUR COACHING TEAM</div><h1>Your coach<span className="title-dot">.</span></h1><p>Get help with your workouts, meals and progress.</p></div><button className="primary-button" disabled={generating || running} onClick={onGenerate}>{generating ? <LoaderCircle size={16} className="spin"/> : <Sparkles size={16}/>}Build my week</button></section>

    {error && <div className="inline-error" role="alert">{error}<button className="quiet-button" onClick={() => void load()}>Retry</button></div>}
    {loading ? <div className="loading-state"><LoaderCircle className="spin"/>Loading your team…</div> : <>
      <div className={`agent-workspace ${!result && !running ? 'awaiting-question' : ''}`}><section className="content-card agent-runner"><div className="card-heading"><div><h3>What can we help with?</h3></div><Play size={18}/></div><form onSubmit={runAgent}>
        <label className="field"><span>Choose a focus</span><select value={selected} onChange={e => { setSelected(e.target.value); setResult(null) }}>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.name.replace(/ Agent$/, '')}</option>)}</select></label>
        <label className="field"><span>What would you like help with? <small>(optional)</small></span><textarea value={message} maxLength={1200} onChange={e => setMessage(e.target.value)} rows={3} placeholder="For example: help me make next week easier to stick to."/></label>
        {selected === 'exercise_feedback' && <label className="field"><span>Movement session</span><select value={poseId} onChange={e => setPoseId(e.target.value)}><option value="">Use latest session, if available</option>{sessions.map(session => <option key={session.id} value={session.id}>#{session.id} · {session.exercise} · {session.reps} reps</option>)}</select><small>Uses measurements saved in Workout studio.</small></label>}
        <p className="runner-note">Uses your saved preferences and recent progress. Changes to your weekly plan always need your approval.</p>
        <button className="primary-button" type="submit" disabled={running || generating}>{running ? <LoaderCircle className="spin" size={16}/> : <Play size={15}/>} {running ? 'Preparing advice…' : 'Get advice'}</button>
      </form></section>{(result || running) && <section className="content-card agent-response" aria-live="polite"><div className="card-heading"><div><h3>{result ? agents.find(a => a.id === result.agent_id)?.name : 'Your next insight'}</h3></div><Sparkles size={18}/></div>{result ? <RunDetails run={result}/> : <div className="agent-result-empty">{running ? <LoaderCircle className="spin" size={26}/> : <Sparkles size={26}/>}<strong>{running ? 'Looking at your context…' : 'A little guidance goes a long way.'}</strong><p>Using your preferences and recent activity.</p></div>}</section>}</div>
      <details className="coach-disclosure"><summary>Previous advice <span>{runs.length} saved runs</span></summary>      <section className="content-card run-history"><div className="card-heading"><div><span className="eyebrow">A RECORD OF YOUR TEAMWORK</span><h3>Recent agent runs</h3></div><button className="text-link" onClick={() => void load()}><RefreshCw size={14}/>Refresh</button></div>{runs.length ? <div className="history-list">{runs.map(run => <details key={run.id}><summary><span className="history-icon"><Clock3 size={16}/></span><span><strong>{agents.find(a => a.id === run.agent_id)?.name || label(run.agent_id)}</strong><small>{new Date(run.created_at.replace(' ', 'T') + (/[Z+]|-\d\d:\d\d$/.test(run.created_at.slice(10)) ? '' : 'Z')).toLocaleString()}</small></span><span className="source-tag">{sourceLabel(run.source)}</span><span className={`run-status ${run.status === 'completed' ? 'result-pass' : ''}`}>{run.status}</span></summary><RunDetails run={run}/></details>)}</div> : <p className="runner-note">Your first run will appear here. Individual runs and coordinated planning steps are both recorded.</p>}</section></details>
      <details className="coach-disclosure"><summary>How the coaching team works <span>Specialists and planning workflow</span></summary>      <section className="agent-map content-card" aria-label="Agent workflow">
        <div className="coordinator-node"><div className="coordinator-icon"><GitBranch size={23}/></div><div><span className="eyebrow">THE BIG PICTURE</span><h2>Central coordinator</h2><p>Your profile + progress → shared context → a plan to review</p></div><span className="schedule-tag">{agents.length} specialists</span></div>
        <div className="flow-arrow"><ArrowDown size={18}/></div>
        <div className="agent-grid">{agents.filter(a => a.id !== 'evaluation_adaptation').map((agent, i) => <button className={`agent-node ${selected === agent.id ? 'selected' : ''}`} key={agent.id} onClick={() => { setSelected(agent.id); setResult(null) }}><span className={`agent-index agent-tint-${i}`}>{String(i + 1).padStart(2, '0')}</span><span><strong>{agent.name}</strong><small>{agent.description}</small></span><ArrowRight size={15}/></button>)}</div>
        <div className="flow-arrow"><ArrowDown size={18}/></div>
        {agents.filter(a => a.id === 'evaluation_adaptation').map(agent => <button key={agent.id} className={`evaluation-node ${selected === agent.id ? 'selected' : ''}`} onClick={() => { setSelected(agent.id); setResult(null) }}><CheckCircle2 size={23}/><span><strong>{agent.name}</strong><small>{agent.description}</small></span><ArrowRight size={17}/></button>)}
        <div className="approval-caption"><Check size={14}/>Draft → your approval → saved plan → progress for next time</div>
      </section>
</details>
      <details className="coach-disclosure"><summary>Connection settings <span>{configured ? 'Model configured' : 'Using local rules'}</span></summary>    <div className="agent-connection"><div><span className="status-orb"/><span>{configured ? 'LLM endpoint configured' : 'Local planning is available'}<small>{configured ? 'Each run shows whether the LLM or local rules produced its answer.' : 'Connect an LLM in the backend environment to use model reasoning.'}</small></span></div><button className="quiet-button" onClick={() => void checkModel()} disabled={checking}>{checking ? <LoaderCircle size={15} className="spin"/> : <RefreshCw size={15}/>}Test LLM connection</button>{modelStatus && <p role="status">{modelStatus}</p>}</div></details>
    </>}
  </div>
}
