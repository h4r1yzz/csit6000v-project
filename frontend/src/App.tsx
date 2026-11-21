import BrandMark from './BrandMark'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, ArrowUpRight, CalendarDays, Camera, CircleHelp, Check, ChevronDown, Clock3, Dumbbell, Flame, GitBranch, LayoutDashboard, LoaderCircle, MessageCircle, Plus, Salad, Settings2, Sparkles, Target, TrendingUp, X } from 'lucide-react'
import { api, ApiError } from './api'
import PoseCoach from './PoseCoach'
import AgentStudio from './AgentStudio'
import Preferences from './Preferences'
import PlanView from './PlanView'
import type { Health, Log, Plan, Profile, PoseSession } from './types'

export const viewRoutes = {
  overview: '#/app',
  plan: '#/week',
  tracker: '#/workout',
  progress: '#/progress',
  profile: '#/preferences',
  agents: '#/advanced',
} as const
export type View = keyof typeof viewRoutes
const sectionTitles: Record<View, string> = {
  overview: 'Home', plan: 'My week', tracker: 'Workout', progress: 'Progress', profile: 'Preferences', agents: 'Advanced',
}
const navIcons = { overview: LayoutDashboard, plan: CalendarDays, tracker: Camera, progress: TrendingUp, profile: Settings2, agents: GitBranch }
type PlanProblem = { message: string; detail?: string; editPreferences?: boolean; staleDraft?: boolean }

function planFailure(error: unknown, approving = false): PlanProblem {
  const detail = error instanceof Error ? error.message : undefined
  if (detail && /no menu meets the recorded dietary and budget constraints/i.test(detail)) {
    return { message: 'We couldn’t find meals that fit your food preferences and budget. Review your preferences and try again.', detail, editPreferences: true }
  }
  if (approving && detail?.includes('no longer meets your current preferences')) {
    return { message: 'This draft no longer fits your preferences. Build a new draft before approving.', detail, editPreferences: true, staleDraft: true }
  }
  return {
    message: approving ? 'We couldn’t approve this draft. Try again.' :
      error instanceof ApiError && error.status === 503
        ? 'We couldn’t finish building your week. Try again in a moment.'
        : 'We couldn’t build your week. Try again.',
    detail,
  }
}

function goTo(view: View) {
  window.location.hash = viewRoutes[view]
}

type Overview = { profile: Profile; stats: { workouts: number; minutes: number; avg_effort: number; total_workouts?: number; total_minutes?: number }; recent_workouts: Log[]; active_plan: Plan | null }
const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function shortDate(value: string) { return new Date(value.replace(' ', 'T') + (value.includes('Z') ? '' : 'Z')).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }
function greeting() { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }

export default function App({ accountId, view, firstRun, focusToday, onLogout }: {
  accountId: number; view: View; firstRun: boolean; focusToday: boolean; onLogout: () => Promise<void>
}) {
  const [signingOut, setSigningOut] = useState(false)
  const setupKey = 'fitpilot-setup-' + accountId
  const [needsSetup, setNeedsSetup] = useState(() => {
    try {
      const saved = localStorage.getItem(setupKey)
      return firstRun ? saved !== 'complete' : saved === 'pending'
    } catch { return firstRun }
  })
  const [overview, setOverview] = useState<Overview | null>(null)
  const [logs, setLogs] = useState<Log[]>([])
  const [profile, setProfile] = useState<Profile | null>(null)
  const [draft, setDraft] = useState<Profile | null>(null)
  const [planDraft, setPlanDraft] = useState<Plan | null>(null)
  const [apiReady, setApiReady] = useState(false)
  const [llmReady, setLlmReady] = useState(false)
  const [pendingAction, setPendingAction] = useState<'build' | 'approve' | 'preferences' | null>(null)
  const busy = pendingAction !== null
  const [planProblem, setPlanProblem] = useState<PlanProblem | null>(null)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [chatOpen, setChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatHistory, setChatHistory] = useState<{ role: string; text: string }[]>([])
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
      const data = await api.get<Overview>('/api/overview')
      setOverview(data); setProfile(data.profile); setDraft(current => current || data.profile)
      setLogs(data.recent_workouts); setApiReady(true); setError('')
      // Secondary history must not hold the entire dashboard behind a spinner.
      const results = await Promise.allSettled([
        api.get<Log[]>('/api/workouts').then(setLogs),
        api.get<Health>('/api/health').then(health => setLlmReady(health.llm_configured)),
        api.get<PoseSession[]>('/api/pose-sessions').then(setPoseSessions),
        Promise.all([api.get<Plan[]>('/api/plans'), api.get<{ id: number; result: Plan | null }[]>('/api/workflows?limit=10')]).then(([plans, workflows]) => {
          setPlanHistory(plans)
          setRecentDrafts(workflows.flatMap(workflow => workflow.result && !plans.some(plan => plan.workflow_id === workflow.id) ? [workflow.result] : []))
        }),
        api.get<{ role: string; text: string; source: string }[]>('/api/assistant/messages').then(messages => setChatHistory(messages.map(item => ({ role: item.role === 'user' ? 'you' : 'coach', text: item.text })))),
      ])
      if (results.some(result => result.status === 'rejected')) setError('Some history could not be loaded. Retry to refresh it.')
      setRevision(value => value + 1)
    } catch (e) { setApiReady(false); setError(e instanceof Error ? e.message : 'Could not connect to FitPilot API. Start the backend to continue.') }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!needsSetup) return
    try { localStorage.setItem(setupKey, 'pending') } catch { /* Setup still works in this visit. */ }
  }, [needsSetup, setupKey])
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

  const activePlan = overview?.active_plan
  const workoutsThisWeek = overview?.stats.workouts ?? 0
  const minutesThisWeek = overview?.stats.minutes ?? 0
  const todayName = dayNames[new Date().getDay()]
  const todayWorkout = activePlan?.content.workouts.find(w => w.day.toLowerCase().startsWith(todayName.toLowerCase()))

  const showSetup = needsSetup && !activePlan

  async function generatePlan() {
    if (busy || showSetup) return
    setPendingAction('build')
    setPlanProblem(null)
    setHistoryPlan(null)
    goTo('plan')
    try {
      const generated = await api.post<Plan>('/api/workflows/plan', {})
      setPlanDraft(generated)
      setRecentDrafts(current => [generated, ...current].slice(0, 10))
      setRevision(value => value + 1)
    } catch (e) {
      setPlanProblem(planFailure(e))
    } finally {
      setPendingAction(null)
    }
  }

  async function approvePlan() {
    if (busy || !planDraft || planDraft.validation?.valid === false || planProblem?.staleDraft) return
    setPendingAction('approve')
    setPlanProblem(null)
    try {
      const saved = await api.post<Plan>('/api/plans', planDraft)
      setPlanDraft(null)
      setOverview(current => current && { ...current, active_plan: saved })
      setToast('Your week is ready')
      if (window.location.hash === viewRoutes.plan) goTo('overview')
      await refresh()
    } catch (e) {
      setPlanProblem(planFailure(e, true))
    } finally {
      setPendingAction(null)
    }
  }

  async function logWorkout(exercise = logExercise, duration = Number(logMinutes), effort = Number(logEffort), notes = '') {
    setLogging(true); setError('')
    try { await api.post('/api/workouts', { exercise, duration_minutes: duration, perceived_effort: effort, notes }); await refresh(); setShowLog(false); setToast('Activity added to your week') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save workout'); throw e }
    finally { setLogging(false) }
  }
  async function saveProfile() {
    if (!draft || busy) return
    setPendingAction('preferences')
    setError('')
    try {
      const saved = await api.put<Profile>('/api/profile', draft)
      setProfile(saved)
      setDraft(saved)
      setPlanDraft(null)
      setHistoryPlan(null)
      setPlanProblem(null)
      setToast('Preferences saved')
      if (needsSetup) {
        setNeedsSetup(false)
        try { localStorage.setItem(setupKey, 'complete') } catch { /* Setup still works in this visit. */ }
        if (window.location.hash.startsWith(viewRoutes.profile)) {
          window.location.replace(viewRoutes.plan)
        }
      }
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save preferences')
    } finally {
      setPendingAction(null)
    }
  }

  async function signOut() {
    if (signingOut) return
    setSigningOut(true)
    try { await onLogout() }
    catch {
      setError('Sign out failed. Please try again.')
      setSigningOut(false)
    }
  }

  async function sendChat(e: React.FormEvent) {
    e.preventDefault(); const message = chatInput.trim(); if (!message || chatBusy || !llmReady) return
    setChatBusy(true); setChatInput(''); setChatHistory(rows => [...rows, { role: 'you', text: message }])
    try { const result = await api.post<{ answer: string }>('/api/assistant/chat', { message }); setChatHistory(rows => [...rows, { role: 'coach', text: result.answer }]) }
    catch { setChatHistory(rows => [...rows, { role: 'coach', text: 'Coaching is unavailable right now. Try again in a moment.' }]) }
    finally { setChatBusy(false) }
  }

  const firstName = profile?.name.split(' ')[0] || 'there'
  const weekDays = useMemo(() => {
    const today = new Date(); const monday = new Date(today); monday.setDate(today.getDate() - ((today.getDay() + 6) % 7))
    return Array.from({ length: 7 }, (_, i) => { const d = new Date(monday); d.setDate(monday.getDate() + i); return { name: dayNames[d.getDay()], date: d.getDate(), today: d.toDateString() === today.toDateString(), key: d.toDateString() } })
  }, [])
  const workoutDates = new Set(logs.map(x => new Date(x.completed_at.replace(' ', 'T') + (x.completed_at.includes('Z') ? '' : 'Z')).toDateString()))

  const homeAction = showSetup ? { text: 'Set preferences', href: viewRoutes.profile } :
    planDraft ? { text: 'Review my draft', href: viewRoutes.plan } :
    todayWorkout ? { text: 'View today’s workout', href: '#/week/today' } :
    activePlan ? { text: 'Open my week', href: viewRoutes.plan } :
    { text: 'Build my week', href: viewRoutes.plan }
  const currentHistory = focusToday ? null : historyPlan
  const draftToReview = !currentHistory && !focusToday ? planDraft : null
  const displayedPlan = currentHistory || draftToReview || activePlan

  function navItem(destination: View) {
    const Icon = navIcons[destination]
    const title = sectionTitles[destination]
    return <a key={destination} href={viewRoutes[destination]} aria-label={title} title={title}
      aria-current={view === destination ? 'page' : undefined}
      className={view === destination ? 'nav-item active' : 'nav-item'}>
      <Icon size={18}/>{title}{destination === 'plan' && activePlan && <i className="nav-dot"/>}
    </a>
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <a href="#home" className="brand" aria-label="FitPilot landing page"><div className="brand-mark"><BrandMark size={28}/></div><span>fitpilot<span className="brand-period">.</span></span></a>
      <div className="workspace-label">YOUR WELLNESS SPACE</div>
      <nav className="side-nav" aria-label="Main navigation">
        {(['overview', 'plan', 'tracker', 'progress'] as const).map(navItem)}
        <div className="nav-rule" />
        {(['profile', 'agents'] as const).map(navItem)}
      </nav>
      <div className="sidebar-spacer" />

      <button className="profile-chip" onClick={() => goTo('profile')}><div className="avatar">{firstName.slice(0, 1).toUpperCase()}</div><span><strong>{profile?.name || 'Your profile'}</strong><small>{profile?.experience || 'Beginner'} journey</small></span><ChevronDown size={15} /></button>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="crumb"><span>FitPilot</span><span className="crumb-slash">/</span><strong>{sectionTitles[view]}</strong></div><div className="topbar-actions"><button className="auth-signout" type="button" disabled={signingOut} onClick={() => void signOut()}>{signingOut ? 'Signing out…' : 'Sign out'}</button><div className="top-avatar">{firstName.slice(0, 1).toUpperCase()}</div></div></header>
      {error && <div className="notice error-notice" role="alert"><span>{apiReady ? error : 'We couldn’t load your dashboard. Please try again.'}</span><button onClick={() => void refresh()}>Retry</button></div>}
      {!apiReady ? <div className="loading-state"><LoaderCircle className="spin" size={24} /><span>Getting your space ready…</span></div> : <>
        {view === 'overview' && <div className="page-content home-page">
          <section className="welcome-row">
            <div>
              <div className="date-eyebrow">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</div>
              <h1>{greeting()}, {firstName}<span className="title-dot">.</span></h1>
              <p className="welcome-copy">Your plan, movement, and progress in one place.</p>
            </div>
          </section>

          <section className="metrics-grid home-metrics">
            <Metric icon={<Dumbbell size={17}/>} label="WORKOUTS" value={`${workoutsThisWeek}`} suffix="sessions" trend="this week" tint="sage"/>
            <Metric icon={<Clock3 size={17}/>} label="TIME MOVING" value={`${minutesThisWeek}`} suffix="minutes" trend="this week" tint="lavender"/>
            <Metric icon={<Flame size={17}/>} label="WEEKLY GOAL" value={`${Math.min(100, Math.round((workoutsThisWeek / Math.max(1, profile?.weekly_days || 4)) * 100))}`} suffix="%" trend={`${profile?.weekly_days || 4} planned days`} tint="peach"/>
          </section>

          <section className="content-card focus-card home-focus">
            <div className="focus-icon"><Target size={20}/></div>
            <div className="focus-main">
              <h2>{showSetup ? 'Set up your first week' : planDraft ? 'Your draft is ready to review' :
                todayWorkout ? todayWorkout.focus : activePlan ? 'Recovery day' : 'Plan your week'}</h2>
              {showSetup ? <span>Review your goals and schedule to build your week.</span> :
                planDraft ? <span>Review your workouts and meals before making the draft active.</span> :
                todayWorkout ? <span>{todayWorkout.duration_minutes} min · {todayWorkout.exercises.slice(0, 3).map(x => x.name).join(' · ')}</span> :
                activePlan ? <span>You have no workout scheduled today.</span> :
                <span>Build a workout and meal draft around your preferences.</span>}
            </div>
            <a className="primary-button" href={homeAction.href} onClick={() => setHistoryPlan(null)}>
              {homeAction.text}<ArrowRight size={16}/>
            </a>
          </section>

          <section className="home-week">
            <div className="content-card week-card">
              <div className="card-heading"><h3>This week</h3><a className="text-link" href={viewRoutes.plan}>Open my week <ArrowRight size={14}/></a></div>
              <div className="week-strip">{weekDays.map(d => {
                const completed = workoutDates.has(d.key)
                const planned = activePlan?.content.workouts.some(w => w.day.toLowerCase().startsWith(d.name.toLowerCase()))
                return <div key={d.key} className={'week-day' + (d.today ? ' today' : '')} aria-label={d.name + ' ' + d.date + (completed ? ', activity logged' : planned ? ', workout planned' : '')}>
                  <span>{d.name}</span>
                  <div className={'day-circle' + (completed ? ' completed' : '') + (d.today ? ' is-today' : '')}>{completed ? <Check size={14}/> : d.date}</div>
                  <i className={planned ? 'plan-mark' : ''}/>
                </div>
              })}</div>
              <div className="week-footer">
                <span><span className="legend-dot done"/>Completed</span><span><span className="legend-dot planned"/>Planned</span>
                <button onClick={() => setShowLog(true)}><Plus size={14}/>Log activity</button>
              </div>
            </div>
          </section>

          <section className="home-grid">
            <div className="content-card recent-card">
              <div className="card-heading">
                <h3>Recent activity</h3>
                <a className="text-link" href={viewRoutes.progress}>All activity <ArrowRight size={14}/></a>
              </div>
              {logs.length ? <div className="activity-list">{logs.slice(0, 3).map(log => <ActivityRow key={log.id} log={log}/>)}</div> :
                <p className="runner-note">Your logged workouts will appear here.</p>}
            </div>

            <div className="content-card meal-card">
              <div className="card-heading"><div><span className="eyebrow">MEAL IDEAS</span><h3>On your plate</h3></div><div className="meal-icon"><Salad size={19}/></div></div>
              {activePlan?.content.meals?.length ? <div className="meal-list">{activePlan.content.meals.slice(0, 3).map((meal, index) => <div className="meal-item" key={meal.name}>
                <div className={`meal-index meal-${index}`}>{String(index + 1).padStart(2, '0')}</div>
                <div><strong>{meal.name}</strong><span>{meal.why}</span></div>
              </div>)}</div> : <div className="meal-empty">Build and approve a week to see meal ideas that fit your preferences.</div>}
              <a className="focus-link meal-link" href={viewRoutes.plan}>View all meal ideas <ArrowRight size={14}/></a>
            </div>
          </section>
        </div>}

        {view === 'plan' && <div className="page-content subpage week-page">
          <section className="subpage-heading">
            <div><h1>My week<span className="title-dot">.</span></h1><p>Review and manage your workouts and meals.</p></div>
            {displayedPlan && !showSetup && !draftToReview && !currentHistory &&
              <button className="quiet-button" disabled={busy} onClick={() => void generatePlan()}>Build a new draft</button>}
          </section>

          {showSetup && <section className="content-card setup-card" aria-label="Finish setup">
            <h2>Finish preferences to build your week</h2>
            <p>Review your goal, schedule, and food preferences first.</p>
            <a className="primary-button" href={viewRoutes.profile}>Set preferences <ArrowRight size={15}/></a>
          </section>}
          {pendingAction === 'build' && <div className="plan-review-banner" role="status"><LoaderCircle className="spin" size={18}/><strong>Building your week…</strong></div>}
          {planProblem && <section className="content-card week-problem">
            <p role="alert">{planProblem.message}</p>
            {planProblem.editPreferences && <a className="text-link" href={viewRoutes.profile}>Edit preferences <ArrowRight size={15}/></a>}
            {planProblem.detail && <details><summary>Technical details</summary><p>{planProblem.detail}</p></details>}
          </section>}
          {currentHistory && <div className="plan-review-banner">
            <strong>Viewing a saved plan{currentHistory.created_at ? ' from ' + shortDate(currentHistory.created_at) : ''}.</strong>
            <button className="text-link" onClick={() => setHistoryPlan(null)}>Back to current week</button>
          </div>}
          {focusToday && planDraft && <a className="text-link" href={viewRoutes.plan}>Back to draft <ArrowRight size={15}/></a>}

          {displayedPlan ? <PlanView plan={displayedPlan}
            key={displayedPlan.workflow_id ?? displayedPlan.id ?? 'week'}
            draft={!!draftToReview}
            busy={busy || showSetup}
            stale={!!draftToReview && !!planProblem?.staleDraft}
            approving={pendingAction === 'approve'}
            focusDay={focusToday ? todayWorkout?.day : undefined}
            onApprove={() => void approvePlan()}
            onDiscard={() => { setPlanDraft(null); setPlanProblem(null) }}
            onRebuild={() => void generatePlan()}/> :
            !showSetup && pendingAction !== 'build' &&
              <section className="empty-plan content-card">
                <div className="empty-plan-illustration"><span className="empty-plan-brand"><BrandMark size={42}/></span><span className="empty-plan-calendar"><CalendarDays size={21}/></span></div>
                <h2>Build your first week</h2>
                <p>Get a workout and meal draft based on your preferences. You approve it before it becomes active.</p>
                <button className="primary-button" disabled={busy} onClick={() => void generatePlan()}>
                  {planProblem && !planProblem.editPreferences ? 'Try again' : 'Build my week'}<ArrowRight size={15}/>
                </button>
              </section>}

          {recentDrafts.length > 0 && <details className="content-card saved-plans">
            <summary>Recent drafts <span>{recentDrafts.length} available</span></summary>
            <div>{recentDrafts.map(plan => <button key={plan.workflow_id} className="saved-plan-item" disabled={busy} onClick={() => {
              setHistoryPlan(null)
              if (planDraft?.workflow_id !== plan.workflow_id) setPlanProblem(null)
              setPlanDraft(plan)
              goTo('plan')
            }}>
              <Sparkles size={16}/><span>{plan.title || 'Weekly draft'}<small>{plan.validation?.valid ? 'Ready to review' : 'Preferences need attention'}</small></span><ArrowRight size={16}/>
            </button>)}</div>
          </details>}
          {planHistory.length > 0 && <details className="content-card saved-plans">
            <summary>Saved plans <span>{planHistory.length} recent</span></summary>
            <div>{planHistory.map(plan => <button key={plan.id} className="saved-plan-item" disabled={busy} onClick={() => {
              setHistoryPlan(plan)
              goTo('plan')
            }}>
              <CalendarDays size={16}/><span>{plan.title}<small>{plan.created_at ? shortDate(plan.created_at) : ''}</small></span><ArrowRight size={16}/>
            </button>)}</div>
          </details>}
        </div>}

        {view === 'progress' && <div className="page-content subpage"><section className="subpage-heading"><div><div className="date-eyebrow"><span className="sun-glyph">✳</span>IT ALL COUNTS</div><h1>Look at you go<span className="title-dot">.</span></h1><p>Progress isn’t a straight line. Here’s what you’ve been building.</p></div><button className="primary-button" onClick={() => setShowLog(true)}><Plus size={16}/>Log activity</button></section><section className="metrics-grid progress-metrics"><Metric icon={<Dumbbell size={17}/>} label="TOTAL SESSIONS" value={`${overview?.stats.total_workouts ?? logs.length}`} suffix="sessions" trend="all time" tint="sage"/><Metric icon={<Clock3 size={17}/>} label="TIME MOVING" value={`${overview?.stats.total_minutes ?? logs.reduce((n, x) => n + x.duration_minutes, 0)}`} suffix="minutes" trend="all time" tint="lavender"/><Metric icon={<Flame size={17}/>} label="AVERAGE EFFORT" value={`${overview?.stats.avg_effort ? Number(overview.stats.avg_effort).toFixed(1) : '—'}`} suffix="/ 10" trend="this week" tint="peach"/></section><div className="content-card progress-card"><div className="card-heading"><div><span className="eyebrow">YOUR RECENT WINS</span><h3>Movement journal</h3></div><span className="journal-count">{logs.length} {logs.length === 1 ? 'entry' : 'entries'}</span></div>{logs.length ? <div className="activity-list large">{logs.map(log => <ActivityRow key={log.id} log={log}/>)}</div> : <div className="progress-empty"><div className="empty-icon"><TrendingUp size={18}/></div><strong>Every beginning is a win.</strong><span>Log a session to start your movement journal.</span><button className="primary-button small" onClick={() => setShowLog(true)}><Plus size={14}/>Log activity</button></div>}</div></div>}

        {view === 'tracker' && <div className="page-content subpage studio-page"><PoseCoach onLog={(exercise, minutes, effort, notes) => logWorkout(exercise, minutes, effort, notes)}/><section className="content-card pose-history"><div className="card-heading"><div><span className="eyebrow">MEASUREMENTS THAT MATTER</span><h3>Recent form checks</h3></div><span className="schedule-tag">{poseSessions.length} saved</span></div>{poseSessions.length ? poseSessions.map(session => <div key={session.id} className="pose-history-row"><div className="activity-symbol"><Camera size={17}/></div><div><strong>{session.exercise}</strong><small>{shortDate(session.created_at)} · {session.source === 'webcam' ? 'Camera' : 'Video clip'} · {Math.round(session.duration_seconds)}s analyzed</small></div><span><strong>{session.reps}</strong> reps</span><span>{Math.round(session.average_confidence * 100)}% visibility</span></div>) : <p className="runner-note">Save a form check to review your measurements and get movement feedback.</p>}</section></div>}
        {view === 'agents' && <AgentStudio revision={revision}/>}
        {view === 'profile' && draft && <Preferences draft={draft} onChange={setDraft} onSave={() => void saveProfile()} busy={busy} firstRun={showSetup}/>}

      </>}
      <footer className="app-footer"><span>Take what feels good. Leave what doesn’t.</span><span><CircleHelp size={13}/> General wellness only · Not medical advice</span></footer>
    </main>

    <button className="coach-fab" onClick={() => setChatOpen(true)} aria-label="Open FitPilot coach"><MessageCircle size={20}/><span>Coach</span></button>
    {chatOpen && <div className="chat-backdrop" onClick={() => setChatOpen(false)}><section role="dialog" aria-modal="true" aria-label="Your FitPilot coach" className="chat-panel" onClick={e => e.stopPropagation()}><div className="chat-head"><div className="coach-avatar"><Sparkles size={17}/></div><div><strong>Your FitPilot coach</strong><span><i className={llmReady ? 'online-dot' : 'offline-dot'}/>{llmReady ? 'Chat about your week' : 'Coaching unavailable'}</span></div><button onClick={() => setChatOpen(false)} aria-label="Close coach"><X size={19}/></button></div><div className="chat-intro"><span className="chat-wave">✳</span><h3>Hey, {firstName}.</h3><p>{llmReady ? 'What’s on your mind today? We can talk through your routine, meal ideas, or a small next step.' : 'Connect the course model in Advanced before starting a coaching conversation.'}</p><div className="suggestion-chips"><button disabled={!llmReady} onClick={() => setChatInput('Can you make my next workout shorter?')}>A shorter workout</button><button disabled={!llmReady} onClick={() => setChatInput('Suggest an affordable high-protein meal.')}>Easy meal idea</button></div></div><div className="chat-messages">{chatHistory.map((item, i) => <div key={i} className={`chat-bubble ${item.role === 'you' ? 'from-user' : 'from-coach'}`}>{item.text}</div>)}{chatBusy && <div className="chat-bubble from-coach" role="status">Coach is thinking…</div>}</div><form className="chat-compose" onSubmit={sendChat}><input aria-label="Message your coach" maxLength={1200} disabled={!llmReady} value={chatInput} onChange={e => setChatInput(e.target.value)} placeholder={llmReady ? 'Ask anything about your plan…' : 'Coaching is unavailable'}/><button disabled={!llmReady || !chatInput.trim() || chatBusy} aria-label="Send message"><ArrowRight size={17}/></button></form><div className="chat-footnote">Wellness guidance, not medical advice.</div></section></div>}
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
