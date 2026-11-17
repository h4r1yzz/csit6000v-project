import BrandMark from './BrandMark'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, ArrowRight, ArrowUpRight, CalendarDays, Camera, CircleHelp, Check, ChevronDown, Clock3, Dumbbell, Flame, GitBranch, LayoutDashboard, LoaderCircle, MessageCircle, Plus, Salad, Settings2, Sparkles, Target, TrendingUp, X } from 'lucide-react'
import { api } from './api'
import PoseCoach from './PoseCoach'
import AgentStudio, { sourceLabel } from './AgentStudio'
import Preferences from './Preferences'
import PlanView from './PlanView'
import type { Health, Log, Plan, Profile, PoseSession } from './types'

type View = 'overview' | 'plan' | 'progress' | 'profile' | 'tracker' | 'agents'
type Overview = { profile: Profile; stats: { workouts: number; minutes: number; avg_effort: number; total_workouts?: number; total_minutes?: number }; recent_workouts: Log[]; active_plan: Plan | null }
const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function shortDate(value: string) { return new Date(value.replace(' ', 'T') + (value.includes('Z') ? '' : 'Z')).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }
function greeting() { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }

export default function App({ initialView = 'overview' }: { initialView?: 'overview' | 'tracker' }) {
  const [view, setView] = useState<View>(initialView)
  const [overview, setOverview] = useState<Overview | null>(null)
  const [logs, setLogs] = useState<Log[]>([])
  const [profile, setProfile] = useState<Profile | null>(null)
  const [draft, setDraft] = useState<Profile | null>(null)
  const [planDraft, setPlanDraft] = useState<Plan | null>(null)
  const [apiReady, setApiReady] = useState(false)
  const [llmReady, setLlmReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [chatOpen, setChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatHistory, setChatHistory] = useState<{ role: string; text: string; source?: string }[]>([])
  const [chatBusy, setChatBusy] = useState(false)
  const [logging, setLogging] = useState(false)
  const [revision, setRevision] = useState(0)
  const [poseSessions, setPoseSessions] = useState<PoseSession[]>([])
  const [planHistory, setPlanHistory] = useState<Plan[]>([])
  const [historyPlan, setHistoryPlan] = useState<Plan | null>(null)
  const [recentDrafts, setRecentDrafts] = useState<Plan[]>([])
  const [showLog, setShowLog] = useState(false)
  const [logExercise, setLogExercise] = useState('Strength training')
  const [logMinutes, setLogMinutes] = useState('30')
  const [logEffort, setLogEffort] = useState('6')

  const refresh = useCallback(async () => {
    try {
      const [data, activity, health, poses, plans, workflows, messages] = await Promise.all([api.get<Overview>('/api/overview'), api.get<Log[]>('/api/workouts'), api.get<Health>('/api/health'), api.get<PoseSession[]>('/api/pose-sessions'), api.get<Plan[]>('/api/plans'), api.get<{ id: number; result: Plan | null }[]>('/api/workflows?limit=10'), api.get<{ role: string; text: string; source: string }[]>('/api/assistant/messages')])
      setOverview(data); setProfile(data.profile); setDraft(current => current || data.profile); setLogs(activity); setPoseSessions(poses); setPlanHistory(plans); setApiReady(true); setLlmReady(health.llm_configured); setError(''); setRevision(value => value + 1)
      setRecentDrafts(workflows.flatMap(workflow => workflow.result && !plans.some(plan => plan.workflow_id === workflow.id) ? [workflow.result] : []))
      setChatHistory(messages.map(item => ({ role: item.role === 'user' ? 'you' : 'coach', text: item.text, source: item.source || undefined })))
    } catch (e) { setApiReady(false); setError(e instanceof Error ? e.message : 'Could not connect to FitPilot API. Start the backend to continue.') }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!chatOpen && !showLog) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    const dialog = document.querySelector<HTMLElement>('[aria-modal="true"]')
    const focusable = () => Array.from(dialog?.querySelectorAll<HTMLElement>('button:not(:disabled), input, select, textarea, [tabindex="0"]') || [])
    focusable()[0]?.focus()
    const keydown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setChatOpen(false); setShowLog(false) }
      if (e.key === 'Tab') { const elements = focusable(); const first = elements[0]; const last = elements[elements.length - 1]; if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() } }
    }
    document.addEventListener('keydown', keydown)
    const overflow = document.body.style.overflow; document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', keydown); document.body.style.overflow = overflow; previouslyFocused?.focus() }
  }, [chatOpen, showLog])
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(''), 2600); return () => window.clearTimeout(timer) }, [toast])

  const workoutsThisWeek = overview?.stats.workouts ?? 0
  const minutesThisWeek = overview?.stats.minutes ?? 0
  const activePlan = overview?.active_plan
  const todayName = dayNames[new Date().getDay()]
  const todayWorkout = activePlan?.content.workouts.find(w => w.day.toLowerCase().startsWith(todayName.toLowerCase()))

  async function generatePlan() {
    if (busy) return
    setBusy(true); setError(''); setHistoryPlan(null); setView('plan')
    try { const generated = await api.post<Plan>('/api/workflows/plan', {}); setPlanDraft(generated); setRecentDrafts(current => [generated, ...current].slice(0, 10)); setRevision(value => value + 1) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not generate a plan') }
    finally { setBusy(false) }
  }
  async function approvePlan() {
    if (!planDraft) return
    setBusy(true); setError('')
    try { await api.post('/api/plans', planDraft); setPlanDraft(null); await refresh(); setToast('Your week is ready. Nice work!') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save your plan') }
    finally { setBusy(false) }
  }
  async function logWorkout(exercise = logExercise, duration = Number(logMinutes), effort = Number(logEffort), notes = '') {
    setLogging(true); setError('')
    try { await api.post('/api/workouts', { exercise, duration_minutes: duration, perceived_effort: effort, notes }); await refresh(); setShowLog(false); setToast('Activity added to your week') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save workout'); throw e }
    finally { setLogging(false) }
  }
  async function saveProfile() {
    if (!draft) return
    setBusy(true); setError('')
    try { const saved = await api.put<Profile>('/api/profile', draft); setProfile(saved); setDraft(saved); await refresh(); setToast('Your preferences are saved') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save preferences') }
    finally { setBusy(false) }
  }
  async function sendChat(e: React.FormEvent) {
    e.preventDefault(); const message = chatInput.trim(); if (!message || chatBusy) return
    setChatBusy(true); setChatInput(''); setChatHistory(rows => [...rows, { role: 'you', text: message }])
    try { const result = await api.post<{ answer: string; source: string }>('/api/assistant/chat', { message }); setChatHistory(rows => [...rows, { role: 'coach', text: result.answer, source: result.source }]) }
    catch { setChatHistory(rows => [...rows, { role: 'coach', text: 'I could not reach the coach right now. Try again after checking that the API is running.' }]) }
    finally { setChatBusy(false) }
  }

  const sectionTitle: Record<View, string> = { overview: 'Your space', plan: 'Your plan', progress: 'Your progress', profile: 'Your preferences', tracker: 'Workout studio', agents: 'Your coaching team' }
  const firstName = profile?.name.split(' ')[0] || 'there'
  const weekDays = useMemo(() => {
    const today = new Date(); const monday = new Date(today); monday.setDate(today.getDate() - ((today.getDay() + 6) % 7))
    return Array.from({ length: 7 }, (_, i) => { const d = new Date(monday); d.setDate(monday.getDate() + i); return { name: dayNames[d.getDay()], date: d.getDate(), today: d.toDateString() === today.toDateString(), key: d.toDateString() } })
  }, [])
  const workoutDates = new Set(logs.map(x => new Date(x.completed_at.replace(' ', 'T') + (x.completed_at.includes('Z') ? '' : 'Z')).toDateString()))

  return <div className="app-shell">
    <aside className="sidebar">
      <a href="#/" className="brand" aria-label="FitPilot landing page"><div className="brand-mark"><BrandMark size={28}/></div><span>fitpilot<span className="brand-period">.</span></span></a>
      <div className="workspace-label">YOUR WELLNESS SPACE</div>
      <nav className="side-nav" aria-label="Main navigation">
        <button aria-label="Overview" title="Overview" className={view === 'overview' ? 'nav-item active' : 'nav-item'} onClick={() => setView('overview')}><LayoutDashboard size={18} />Overview</button>
        <button aria-label="My week" title="My week" className={view === 'plan' ? 'nav-item active' : 'nav-item'} onClick={() => setView('plan')}><CalendarDays size={18} />My week{activePlan && <i className="nav-dot" />}</button>
        <button aria-label="Workout studio" title="Workout studio" className={view === 'tracker' ? 'nav-item active' : 'nav-item'} onClick={() => setView('tracker')}><Camera size={18}/>Workout studio</button>
        <button aria-label="Coaching team" title="Coaching team" className={view === 'agents' ? 'nav-item active' : 'nav-item'} onClick={() => setView('agents')}><GitBranch size={18}/>Coaching team</button>
        <button aria-label="Progress" title="Progress" className={view === 'progress' ? 'nav-item active' : 'nav-item'} onClick={() => setView('progress')}><TrendingUp size={18} />Progress</button>
        <div className="nav-rule" />
        <button aria-label="Preferences" title="Preferences" className={view === 'profile' ? 'nav-item active' : 'nav-item'} onClick={() => setView('profile')}><Settings2 size={18} />Preferences</button>
      </nav>
      <div className="sidebar-spacer" />

      <button className="profile-chip" onClick={() => setView('profile')}><div className="avatar">{firstName.slice(0, 1).toUpperCase()}</div><span><strong>{profile?.name || 'Your profile'}</strong><small>{profile?.experience || 'Beginner'} journey</small></span><ChevronDown size={15} /></button>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="crumb"><span>FitPilot</span><span className="crumb-slash">/</span><strong>{sectionTitle[view]}</strong></div><div className="topbar-actions"><div className="top-avatar">{firstName.slice(0, 1).toUpperCase()}</div></div></header>
      {error && <div className="notice error-notice"><span>{apiReady ? error : 'We couldn’t load your dashboard. Please try again.'}</span><button onClick={() => void refresh()}>Retry</button></div>}
      {!apiReady ? <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>Getting your space ready…</span></div> : <>
        {view === 'overview' && <div className="page-content">
          <section className="welcome-row"><div><div className="date-eyebrow"><span className="sun-glyph">✳</span>{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }).toUpperCase()}</div><h1>{greeting()}, {firstName}<span className="title-dot">.</span></h1><p className="welcome-copy">A little progress goes a long way. Here’s your week, at a glance.</p></div><button className="primary-button" onClick={() => setView('tracker')}><Camera size={16} />Start a workout</button></section>

          <section className="metrics-grid"><Metric icon={<Dumbbell size={17}/>} label="WORKOUTS" value={`${workoutsThisWeek}`} suffix="sessions" trend="this week" tint="sage"/><Metric icon={<Clock3 size={17}/>} label="TIME MOVING" value={`${minutesThisWeek}`} suffix="minutes" trend="this week" tint="lavender"/><Metric icon={<Flame size={17}/>} label="WEEKLY RHYTHM" value={`${Math.min(100, Math.round((workoutsThisWeek / Math.max(1, profile?.weekly_days || 4)) * 100))}`} suffix="%" trend="of your goal" tint="peach"/></section>

          <section className="dashboard-grid"><div className="content-card week-card"><div className="card-heading"><div><span className="eyebrow">YOUR ROUTINE</span><h3>This week</h3></div><button className="text-link" onClick={() => setView('plan')}>See plan <ArrowRight size={14}/></button></div><div className="week-strip">{weekDays.map(d => <div key={d.key} className={`week-day ${d.today ? 'today' : ''}`}><span>{d.name}</span><div className={`day-circle ${workoutDates.has(d.key) ? 'completed' : ''} ${d.today ? 'is-today' : ''}`}>{workoutDates.has(d.key) ? <Check size={14}/> : d.date}</div><i className={activePlan?.content.workouts.some(w => w.day.toLowerCase().startsWith(d.name.toLowerCase())) ? 'plan-mark' : ''}/></div>)}</div><div className="week-footer"><span><span className="legend-dot done"/>Completed</span><span><span className="legend-dot planned"/>Planned</span><button onClick={() => setShowLog(true)}><Plus size={14}/>Log activity</button></div></div>
          <div className="content-card focus-card"><div className="card-heading"><div><span className="eyebrow">A GOOD PLACE TO START</span><h3>Today’s focus</h3></div><div className="focus-icon"><Target size={18}/></div></div>{todayWorkout ? <><div className="focus-main"><span className="focus-time"><Clock3 size={14}/>{todayWorkout.duration_minutes} min</span><strong>{todayWorkout.focus}</strong><span>{todayWorkout.exercises.slice(0, 3).map(x => x.name).join(' · ')}</span></div><button className="focus-link" onClick={() => setView('plan')}>View session <ArrowRight size={14}/></button></> : <><div className="focus-main empty-focus"><strong>{activePlan ? 'A recovery day' : 'Make it your own'}</strong><span>{activePlan ? 'Your next workout is waiting in My week.' : 'A plan shaped around your time, gear, and goals.'}</span></div><button className="focus-link" disabled={busy} onClick={() => activePlan ? setView('plan') : void generatePlan()}>{busy ? 'Putting it together…' : activePlan ? 'See your week' : 'Create a weekly plan'} <ArrowRight size={14}/></button></>}</div></section>

          <section className="bottom-grid"><div className="content-card recent-card"><div className="card-heading"><div><span className="eyebrow">YOU SHOWED UP</span><h3>Recent movement</h3></div><button className="text-link" onClick={() => setView('progress')}>All activity <ArrowRight size={14}/></button></div>{logs.length ? <div className="activity-list">{logs.slice(0, 3).map(log => <ActivityRow key={log.id} log={log}/>)}</div> : <div className="empty-row"><div className="empty-icon"><Activity size={18}/></div><span>Your movement will show up here.<br/><strong>Every session counts.</strong></span><button onClick={() => setShowLog(true)}>Add your first</button></div>}</div><div className="content-card meal-card"><div className="card-heading"><div><span className="eyebrow">FUEL THAT FEELS GOOD</span><h3>On your plate</h3></div><div className="meal-icon"><Salad size={19}/></div></div>{activePlan?.content.meals?.length ? <div className="meal-list">{activePlan.content.meals.slice(0, 2).map((meal, i) => <div className="meal-item" key={meal.name}><div className={`meal-index meal-${i}`}>{i === 0 ? '01' : '02'}</div><div><strong>{meal.name}</strong><span>{meal.why}</span></div></div>)}</div> : <div className="meal-empty">A few balanced ideas, made around what works for you.</div>}<button className="focus-link meal-link" onClick={() => setView('plan')}>Explore your meal ideas <ArrowRight size={14}/></button></div></section>
        </div>}

        {view === 'plan' && <div className="page-content subpage"><section className="subpage-heading"><div><div className="date-eyebrow"><span className="sun-glyph">✳</span>MADE FOR YOUR REAL LIFE</div><h1>Your week, your way<span className="title-dot">.</span></h1><p>Movement and meals that fit into the life you already have.</p></div><button className="primary-button" disabled={busy} onClick={() => void generatePlan()}>{busy ? <LoaderCircle className="spin" size={16}/> : <Sparkles size={16}/>} {activePlan ? 'Refresh my plan' : 'Build my week'}</button></section>
          {busy && (activePlan || planDraft) && <div className="plan-review-banner" role="status"><LoaderCircle className="spin" size={18}/><strong>Your team is working. A new draft will appear here when all five steps finish.</strong></div>}
          {historyPlan && <div className="plan-review-banner"><strong>Viewing a saved plan from {historyPlan.created_at ? shortDate(historyPlan.created_at) : 'your history'}.</strong><button className="text-link" onClick={() => setHistoryPlan(null)}>Back to current plan</button></div>}
          {historyPlan ? <PlanView plan={historyPlan}/> : planDraft ? <PlanView plan={planDraft} draft busy={busy} onApprove={() => void approvePlan()} onDiscard={() => setPlanDraft(null)}/> : activePlan ? <PlanView plan={activePlan}/> : busy ? <div className="empty-plan content-card" role="status"><LoaderCircle className="spin" size={32}/><h2>Your team is planning…</h2><p>The coordinator is gathering your goals, exercise plan, meal ideas and progress before checking your constraints.</p></div> : <div className="empty-plan content-card"><div className="empty-plan-illustration"><CalendarDays size={33}/><Sparkles size={17}/></div><h2>Your next chapter starts with a plan.</h2><p>Share what you’re working toward and FitPilot will sketch out a flexible week. You’ll get to review everything before it’s saved.</p><button className="primary-button" disabled={busy} onClick={() => void generatePlan()}>{busy ? 'Making your plan…' : 'Create a plan for me'}<ArrowRight size={15}/></button><small>Uses your preferences. You’re always in control.</small></div>}
          {recentDrafts.length > 0 && <details className="content-card saved-plans"><summary>Recent planning drafts <span>{recentDrafts.length} available</span></summary><div>{recentDrafts.map(plan => <button key={plan.workflow_id} className="saved-plan-item" disabled={busy} onClick={() => { setHistoryPlan(null); setPlanDraft(plan) }}><Sparkles size={16}/><span>Workflow #{plan.workflow_id}<small>{sourceLabel(plan.source)} · {plan.validation?.valid ? 'Ready to review' : 'Constraints need attention'}</small></span><ArrowRight size={15}/></button>)}</div></details>}
          {planHistory.length > 0 && <details className="content-card saved-plans"><summary>Saved plans <span>{planHistory.length} recent</span></summary><div>{planHistory.map(plan => <button key={plan.id} className="saved-plan-item" disabled={busy} onClick={() => { setHistoryPlan(plan) }}><CalendarDays size={16}/><span>{plan.title}<small>{plan.created_at ? shortDate(plan.created_at) : ''} · {sourceLabel(plan.source)}</small></span><ArrowRight size={15}/></button>)}</div></details>}
        </div>}

        {view === 'progress' && <div className="page-content subpage"><section className="subpage-heading"><div><div className="date-eyebrow"><span className="sun-glyph">✳</span>IT ALL COUNTS</div><h1>Look at you go<span className="title-dot">.</span></h1><p>Progress isn’t a straight line. Here’s what you’ve been building.</p></div><button className="primary-button" onClick={() => setShowLog(true)}><Plus size={16}/>Log activity</button></section><section className="metrics-grid progress-metrics"><Metric icon={<Dumbbell size={17}/>} label="TOTAL SESSIONS" value={`${overview?.stats.total_workouts ?? logs.length}`} suffix="sessions" trend="all time" tint="sage"/><Metric icon={<Clock3 size={17}/>} label="TIME MOVING" value={`${overview?.stats.total_minutes ?? logs.reduce((n, x) => n + x.duration_minutes, 0)}`} suffix="minutes" trend="all time" tint="lavender"/><Metric icon={<Flame size={17}/>} label="AVERAGE EFFORT" value={`${overview?.stats.avg_effort ? Number(overview.stats.avg_effort).toFixed(1) : '—'}`} suffix="/ 10" trend="this week" tint="peach"/></section><div className="content-card progress-card"><div className="card-heading"><div><span className="eyebrow">YOUR RECENT WINS</span><h3>Movement journal</h3></div><span className="journal-count">{logs.length} {logs.length === 1 ? 'entry' : 'entries'}</span></div>{logs.length ? <div className="activity-list large">{logs.map(log => <ActivityRow key={log.id} log={log}/>)}</div> : <div className="progress-empty"><div className="empty-icon"><TrendingUp size={18}/></div><strong>Every beginning is a win.</strong><span>Log a session to start your movement journal.</span><button className="primary-button small" onClick={() => setShowLog(true)}><Plus size={14}/>Log activity</button></div>}</div></div>}

        {view === 'tracker' && <div className="page-content subpage studio-page"><PoseCoach onLog={(exercise, minutes, effort, notes) => logWorkout(exercise, minutes, effort, notes)}/><section className="content-card pose-history"><div className="card-heading"><div><span className="eyebrow">MEASUREMENTS THAT MATTER</span><h3>Recent form checks</h3></div><span className="schedule-tag">{poseSessions.length} saved</span></div>{poseSessions.length ? poseSessions.map(session => <div key={session.id} className="pose-history-row"><div className="activity-symbol"><Camera size={17}/></div><div><strong>{session.exercise}</strong><small>{shortDate(session.created_at)} · {session.source === 'webcam' ? 'Camera' : 'Video clip'} · {Math.round(session.duration_seconds)}s analyzed</small></div><span><strong>{session.reps}</strong> reps</span><span>{Math.round(session.average_confidence * 100)}% visibility</span></div>) : <p className="runner-note">Save a form check to make your measurements available to the feedback and adaptation agents.</p>}</section></div>}
        {view === 'agents' && <AgentStudio onGenerate={() => void generatePlan()} generating={busy} configured={llmReady} revision={revision}/>}
        {view === 'profile' && draft && <Preferences draft={draft} onChange={setDraft} onSave={() => void saveProfile()} busy={busy}/>}

      </>}
      <footer className="app-footer"><span>Take what feels good. Leave what doesn’t.</span><span><CircleHelp size={13}/> General wellness only · Not medical advice</span></footer>
    </main>

    <button className="coach-fab" onClick={() => setChatOpen(true)} aria-label="Open FitPilot coach"><MessageCircle size={20}/><span>Coach</span></button>
    {chatOpen && <div className="chat-backdrop" onClick={() => setChatOpen(false)}><section role="dialog" aria-modal="true" aria-label="Your FitPilot coach" className="chat-panel" onClick={e => e.stopPropagation()}><div className="chat-head"><div className="coach-avatar"><Sparkles size={17}/></div><div><strong>Your FitPilot coach</strong><span><i className={llmReady ? 'online-dot' : 'offline-dot'}/>{llmReady ? 'LLM configured' : 'Local coaching'}</span></div><button onClick={() => setChatOpen(false)} aria-label="Close coach"><X size={19}/></button></div><div className="chat-intro"><span className="chat-wave">✳</span><h3>Hey, {firstName}.</h3><p>What’s on your mind today? We can talk through your routine, meal ideas, or a small next step.</p><div className="suggestion-chips"><button onClick={() => setChatInput('Can you make my next workout shorter?')}>A shorter workout</button><button onClick={() => setChatInput('Suggest an affordable high-protein meal.')}>Easy meal idea</button></div></div><div className="chat-messages">{chatHistory.map((item, i) => <div key={i} className={`chat-bubble ${item.role === 'you' ? 'from-user' : 'from-coach'}`}>{item.text}{item.source && <small className="chat-source">{sourceLabel(item.source)}</small>}</div>)}{chatBusy && <div className="chat-bubble from-coach" role="status">Coach is thinking…</div>}</div><form className="chat-compose" onSubmit={sendChat}><input aria-label="Message your coach" maxLength={1200} value={chatInput} onChange={e => setChatInput(e.target.value)} placeholder="Ask anything about your plan…"/><button disabled={!chatInput.trim() || chatBusy} aria-label="Send message"><ArrowRight size={17}/></button></form><div className="chat-footnote">Wellness guidance, not medical advice.</div></section></div>}
    {showLog && <div className="modal-backdrop" onClick={() => setShowLog(false)}><form role="dialog" aria-modal="true" aria-label="Log activity" className="log-modal" onSubmit={e => { e.preventDefault(); void logWorkout().catch(() => undefined) }} onClick={e => e.stopPropagation()}><div className="modal-head"><div className="modal-symbol"><Dumbbell size={19}/></div><button type="button" onClick={() => setShowLog(false)} aria-label="Close"><X size={19}/></button></div><span className="eyebrow">GIVE YOURSELF CREDIT</span><h2>Log some movement</h2><p>It doesn’t have to be a big workout to count.</p>{error && <div className="inline-error" role="alert">{error}</div>}<label className="field"><span>What did you do?</span><input required minLength={2} maxLength={100} value={logExercise} onChange={e => setLogExercise(e.target.value)} /></label><div className="modal-fields"><label className="field"><span>Minutes</span><input type="number" required min="1" max="300" value={logMinutes} onChange={e => setLogMinutes(e.target.value)}/></label><label className="field"><span>Effort · 1 to 10</span><input type="number" required min="1" max="10" value={logEffort} onChange={e => setLogEffort(e.target.value)}/></label></div><button className="primary-button modal-submit" type="submit" disabled={logging}><Check size={16}/>{logging ? 'Saving…' : 'Save this win'}</button></form></div>}
    {toast && <div className="toast" role="status"><Check size={16}/>{toast}</div>}
  </div>
}

function Metric({ icon, label, value, suffix, trend, tint }: { icon: React.ReactNode; label: string; value: string; suffix: string; trend: string; tint: string }) {
  return <div className="metric-card"><div className={`metric-icon ${tint}`}>{icon}</div><span className="metric-label">{label}</span><div className="metric-value">{value}<small>{suffix}</small></div><div className="metric-trend"><span className="trend-arrow"><ArrowUpRight size={13}/></span>{trend}</div></div>
}
function ActivityRow({ log }: { log: Log }) {
  return <div className="activity-row"><div className="activity-symbol"><Dumbbell size={16}/></div><div className="activity-title"><strong>{log.exercise}</strong><span>{log.notes || `${log.perceived_effort}/10 effort`}</span></div><div className="activity-duration"><strong>{log.duration_minutes}<small> min</small></strong><span>{shortDate(log.completed_at)}</span></div><div className="activity-effort"><span>EFFORT</span><strong>{log.perceived_effort}<small>/10</small></strong></div></div>
}
