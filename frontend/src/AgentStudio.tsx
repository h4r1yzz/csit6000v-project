import { useCallback, useEffect, useState } from 'react'
import { ArrowDown, ArrowRight, Check, CheckCircle2, Clock3, GitBranch, LoaderCircle, Play, RefreshCw, Sparkles, XCircle } from 'lucide-react'
import { api } from './api'
import type { Agent, AgentRun, PoseSession } from './types'

export function sourceLabel(source: string) {
  if (source === 'local_fallback' || source === 'offline' || source === 'local') return 'Legacy local'
  if (source === 'mixed') return 'Mixed model sources'
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

export default function AgentStudio({ revision }: { revision: number }) {
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
  const activeAgent = agents.find(agent => agent.id === selected)
  const resultAgent = result ? agents.find(agent => agent.id === result.agent_id) : undefined
  const specialistName = (agent: Agent) => agent.name.replace(/ Agent$/, '').replace('Evaluation and Adaptation', 'Adaptation')

  return <div className="page-content subpage coaching-page">
    <section className="advanced-heading">
      <div><div className="date-eyebrow"><GitBranch size={14}/>REVIEWER TOOLS</div><h1>Advanced<span className="title-dot">.</span></h1><p>Test each specialist and inspect the recorded response.</p></div>
      <span className="advanced-run-count">{runs.length} recorded runs</span>
    </section>

    {error && <div className="inline-error" role="alert">{error}<button className="quiet-button" onClick={() => void load()}>Retry</button></div>}
    {loading ? <div className="loading-state"><LoaderCircle className="spin"/>Loading your team…</div> : <>
      <div className="specialist-tabs" role="tablist" aria-label="Choose a specialist">
        {agents.map((agent, index) => <button type="button" role="tab" aria-selected={selected === agent.id} className={selected === agent.id ? 'selected' : ''} key={agent.id} onClick={() => { setSelected(agent.id); setResult(null) }}>
          <span>{String(index + 1).padStart(2, '0')}</span>{specialistName(agent)}
        </button>)}
      </div>

      <div className="command-grid">
        <section className="content-card command-panel">
          <div className="command-panel-heading"><div className="command-symbol"><Play size={16}/></div><div><span>COMMAND COMPOSER</span><h2>{activeAgent ? specialistName(activeAgent) : 'Choose a specialist'}</h2></div></div>
          <p className="command-description">{activeAgent?.description}</p>
          <form onSubmit={runAgent}>
        <label className="field"><span>Additional context <small>(optional)</small></span><textarea value={message} maxLength={1200} onChange={e => setMessage(e.target.value)} rows={5} placeholder="Add a question or instruction for this run…"/></label>
        {selected === 'exercise_feedback' && <label className="field"><span>Movement session</span><select value={poseId} onChange={e => setPoseId(e.target.value)}><option value="">Use latest session, if available</option>{sessions.map(session => <option key={session.id} value={session.id}>#{session.id} · {session.exercise} · {session.reps} reps</option>)}</select><small>Uses measurements saved in Workout.</small></label>}
        <p className="runner-note">Uses your saved preferences and recent progress. It cannot activate a weekly plan.</p>
        <button className="primary-button command-run" type="submit" disabled={running}>{running ? <LoaderCircle className="spin" size={16}/> : <Play size={15}/>} {running ? 'Running specialist…' : 'Run specialist'}</button>
          </form>
        </section>

        <section className="content-card command-result" aria-live="polite">
          <div className="result-heading"><div><span>LATEST RESPONSE</span><h2>{result ? resultAgent ? specialistName(resultAgent) : label(result.agent_id) : 'Ready for a new run'}</h2></div>{result && <span className={`run-status ${result.status === 'completed' ? 'result-pass' : ''}`}>{result.status}</span>}</div>
          {result ? <RunDetails run={result}/> : <div className="command-empty">{running ? <LoaderCircle className="spin" size={28}/> : <Sparkles size={25}/>}<strong>{running ? 'Reviewing saved context…' : 'The response will appear here'}</strong><p>{running ? 'This can take a moment while the specialist works.' : 'Choose a specialist, add any context, and run it.'}</p></div>}
        </section>
      </div>

      <section className="content-card audit-log">
        <div className="audit-heading"><div><span>RUN HISTORY</span><h2>Recent specialist runs</h2></div><button className="text-link" onClick={() => void load()}><RefreshCw size={14}/>Refresh</button></div>
        {runs.length ? <div className="audit-list">
          <div className="audit-columns" aria-hidden="true"><span>Specialist</span><span>Status</span><span>Source</span><span>Time</span><span/></div>
          {runs.map(run => <details key={run.id} className="audit-row"><summary>
            <span className="audit-agent"><i><Clock3 size={14}/></i><strong>{agents.find(agent => agent.id === run.agent_id)?.name || label(run.agent_id)}</strong></span>
            <span className={`run-status ${run.status === 'completed' ? 'result-pass' : ''}`}>{run.status}</span>
            <span className="source-tag">{sourceLabel(run.source)}</span>
            <time>{new Date(run.created_at.replace(' ', 'T') + (/[Z+]|-\d\d:\d\d$/.test(run.created_at.slice(10)) ? '' : 'Z')).toLocaleString()}</time>
            <span className="audit-view">View</span>
          </summary><RunDetails run={run}/></details>)}
        </div> : <div className="audit-empty"><Clock3 size={18}/><span>Your first specialist run will appear here.</span></div>}
      </section>

      <details className="coach-disclosure architecture-disclosure"><summary>Architecture and workflow <span>Coordinator → specialists → review</span></summary><section className="agent-map content-card" aria-label="Agent workflow">
        <div className="coordinator-node"><div className="coordinator-icon"><GitBranch size={23}/></div><div><span className="eyebrow">THE BIG PICTURE</span><h2>Central coordinator</h2><p>Your profile + progress → shared context → a plan to review</p></div><span className="schedule-tag">{agents.length} specialists</span></div>
        <div className="flow-arrow"><ArrowDown size={18}/></div>
        <div className="agent-grid">{agents.filter(a => a.id !== 'evaluation_adaptation').map((agent, i) => <button className={`agent-node ${selected === agent.id ? 'selected' : ''}`} key={agent.id} onClick={() => { setSelected(agent.id); setResult(null) }}><span className={`agent-index agent-tint-${i}`}>{String(i + 1).padStart(2, '0')}</span><span><strong>{agent.name}</strong><small>{agent.description}</small></span><ArrowRight size={15}/></button>)}</div>
        <div className="flow-arrow"><ArrowDown size={18}/></div>
        {agents.filter(a => a.id === 'evaluation_adaptation').map(agent => <button key={agent.id} className={`evaluation-node ${selected === agent.id ? 'selected' : ''}`} onClick={() => { setSelected(agent.id); setResult(null) }}><CheckCircle2 size={23}/><span><strong>{agent.name}</strong><small>{agent.description}</small></span><ArrowRight size={17}/></button>)}
        <div className="approval-caption"><Check size={14}/>Draft → your approval → saved plan → progress for next time</div>
      </section>
</details>
    </>}
  </div>
}
