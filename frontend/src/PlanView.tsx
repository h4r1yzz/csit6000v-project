import { useEffect, useRef } from 'react'
import { Activity, ArrowRight, CalendarDays, Check, Clock3, Heart, Salad, TrendingUp, XCircle } from 'lucide-react'
import type { Plan, Validation } from './types'
import { sourceLabel, WorkflowTrace } from './AgentStudio'

const checkLabels: Record<string, string> = {
  schedule: 'Preferred days',
  session_time: 'Time per workout',
  equipment_and_catalog: 'Exercise and equipment fit',
  diet_and_allergies: 'Food preferences and allergies',
  catalog_nutrition_and_prices: 'Meal nutrition and prices',
  weekly_servings: 'Weekly servings',
  weekly_budget: 'Weekly food budget',
}

type Props = {
  plan: Plan
  draft: boolean
  busy: boolean
  stale: boolean
  approving: boolean
  focusDay?: string
  onApprove: () => void
  onDiscard: () => void
  onRebuild: () => void
}

function ValidationChecks({ checks }: { checks: Validation['checks'] }) {
  return <ul className="validation-grid plan-checks">
    {checks.map(check => <li key={check.name} className={check.passed ? 'check-pass' : 'check-fail'}>
      {check.passed ? <Check size={15}/> : <XCircle size={15}/>}
      <span>
        <strong>{checkLabels[check.name] ?? check.name.replace(/_/g, ' ')}</strong>
        <small>{check.detail}</small>
      </span>
    </li>)}
  </ul>
}

export default function PlanView({ plan, draft, busy, stale, approving, focusDay, onApprove, onDiscard, onRebuild }: Props) {
  const focusedWorkout = useRef<HTMLElement>(null)
  useEffect(() => {
    if (!focusDay) return
    focusedWorkout.current?.focus({ preventScroll: true })
    focusedWorkout.current?.scrollIntoView({ block: 'start' })
  }, [focusDay])

  const content = plan.content
  const money = (value: number) => new Intl.NumberFormat('en-US', {
    style: 'currency', currency: content.budget_currency || 'USD',
  }).format(value)
  const invalid = plan.validation?.valid === false
  const blocked = invalid || stale
  const notes = plan.clarification ?? []

  return <div className="plan-layout">
    {invalid && <section className="content-card week-problem" aria-labelledby="draft-problem">
      <h2 id="draft-problem">This plan needs changes</h2>
      <p>Some parts of this plan don’t fit your preferences.</p>
      <ValidationChecks checks={plan.validation?.checks.filter(check => !check.passed) ?? []}/>
      <a className="text-link" href="#/preferences">Edit preferences <ArrowRight size={15}/></a>
    </section>}

    <section className="plan-summary content-card">
      <div className="plan-summary-copy">
        {draft && <span className="eyebrow">DRAFT</span>}
        <h2>{plan.title || 'Your weekly plan'}</h2>
        <p>{content.summary}</p>
        <div className="plan-meta">
          <span><CalendarDays size={14}/>{content.workouts.length} workout days</span>
          <span><Clock3 size={14}/>{content.workouts.reduce((n, workout) => n + workout.duration_minutes, 0)} min total</span>
        </div>
      </div>
    </section>

    {notes.length > 0 && <section className="content-card week-advice">
      <h3>Suggestions for your preferences</h3>
      <ul>{notes.map((note, i) => <li key={i}>{note}</li>)}</ul>
      {!invalid && <a className="text-link" href="#/preferences">Edit preferences <ArrowRight size={15}/></a>}
    </section>}

    <section className="content-card schedule-card">
      <div className="card-heading">
        <h3>Workouts</h3>
        <span className="schedule-tag"><Activity size={13}/>{content.workouts.length} sessions</span>
      </div>
      <div className="workout-schedule">
        {content.workouts.map((workout, i) => {
          const focused = focusDay === workout.day
          return <article className={'workout-day' + (focused ? ' workout-day-focused' : '')} key={workout.day}
            ref={focused ? focusedWorkout : undefined} tabIndex={focused ? -1 : undefined} aria-label={workout.day + ' workout'}>
            <div className="workout-day-meta">
              <div className="workout-day-number">{i + 1}</div><span>{workout.day}</span>
            </div>
            <div className="workout-main">
              <strong>{workout.focus}</strong><span>{workout.duration_minutes} minutes</span>
              <div className="exercise-prescriptions">{workout.exercises.map((exercise, j) => <div key={j}>
                <strong>{exercise.name}</strong>
                <span>{exercise.sets} sets × {exercise.reps}{exercise.rest_seconds != null ? ' · ' + exercise.rest_seconds + 's rest' : ''}</span>
              </div>)}</div>
            </div>
          </article>
        })}
      </div>
    </section>

    <section className="content-card meals-card">
      <div className="card-heading"><h3>Meal ideas</h3><div className="meal-icon"><Salad size={19}/></div></div>
      {content.estimated_weekly_cost != null && <p className="meal-budget">
        Estimated weekly cost <strong>{money(content.estimated_weekly_cost)}</strong><span>Catalog prices · selected servings</span>
      </p>}
      <div className="meal-grid">{content.meals.map((meal, i) => <div className="plan-meal" key={meal.name + '-' + i}>
        <div className="meal-plate"><Salad size={18}/></div>
        <div>
          <strong>{meal.name}</strong><span>{meal.why}</span>
          {meal.calories != null && <span className="meal-nutrition">{meal.calories} kcal · {meal.protein_g}g protein / serving</span>}
          {meal.cost != null && <span>{money(meal.cost)} / serving · {meal.servings_per_week || 1} this week</span>}
          {meal.ingredients && <span className="meal-ingredients">{Array.isArray(meal.ingredients) ? meal.ingredients.join(', ') : meal.ingredients}</span>}
        </div>
      </div>)}</div>
      {!content.meals.length && <p className="runner-note">There are no meal ideas for these preferences.</p>}
    </section>

    <div className="plan-notes">
      <div className="adapt-note"><TrendingUp size={18}/><span><strong>Adjusting your week</strong>{content.adaptation_note}</span></div>
      <div className="safety-note"><Heart size={18}/><span>{content.safety_note}</span></div>
    </div>

    {plan.validation && <details className="content-card saved-plans validation-card">
      <summary>Preference checks <span>{invalid ? 'Needs changes' : 'Passed'}</span></summary>
      <ValidationChecks checks={plan.validation.checks}/>
    </details>}
    <details className="content-card saved-plans">
      <summary>How this plan was built</summary>
      <div className="plan-technical">
        <span className="source-tag">{sourceLabel(plan.source)}</span>
        {plan.workflow_id != null && <span className="schedule-tag">Workflow #{plan.workflow_id}</span>}
        {plan.steps?.length ? <WorkflowTrace runs={plan.steps}/> : null}
      </div>
    </details>

    {draft && <div className="plan-approval draft-actions">
      <span>{blocked ? 'Build a valid draft before approving.' : 'Approve to make this your active week.'}</span>
      <div>
        <button className="quiet-button" disabled={busy} onClick={onDiscard}>Close draft</button>
        {blocked && <button className="quiet-button" disabled={busy} onClick={onRebuild}>Build a new draft</button>}
        <button className="primary-button" disabled={busy || blocked} onClick={onApprove}>
          {approving ? 'Approving…' : 'Approve my week'} <ArrowRight size={15}/>
        </button>
      </div>
    </div>}
  </div>
}
