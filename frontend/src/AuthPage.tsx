import { useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import { Activity, ArrowLeft, ArrowRight, CalendarDays, Check, Dumbbell, Eye, EyeOff, Sparkles } from 'lucide-react'
import { api } from './api'
import BrandMark from './BrandMark'
import './auth.css'

export default function AuthPage({ initialRegister, onSuccess }: { initialRegister: boolean; onSuccess: (registered: boolean) => void }) {
  const [registering, setRegistering] = useState(initialRegister)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    const data = new FormData(event.currentTarget)
    const email = String(data.get('email')).trim()
    const password = String(data.get('password'))
    setError('')
    setPending(true)
    try {
      if (registering) {
        await api.post('/api/auth/register', { name: String(data.get('name')).trim(), email, password })
      } else {
        await api.post('/api/auth/login', { email, password })
      }
      onSuccess(registering)
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : 'Please try again.')
      setPending(false)
    }
  }

  return (
    <main className="auth-shell">
      <aside className="auth-showcase" aria-hidden="true">
        <div className="auth-showcase-glow" />
        <a className="auth-showcase-brand auth-enter" style={{ '--auth-delay': '0ms' } as CSSProperties} href="#home"><BrandMark size={28}/><span>fitpilot<span>.</span></span></a>
        <div className="auth-showcase-copy">
          <span className="auth-kicker auth-enter" style={{ '--auth-delay': '60ms' } as CSSProperties}>YOUR ROUTINE, CONNECTED</span>
          <div key={registering ? 'register' : 'login'} className="auth-copy-swap">
            <h2>{registering ? 'Start where your goals begin.' : 'Pick up where you left off.'}</h2>
            <p>{registering
              ? 'Create an account to save preferences, plans, and movement sessions in one place.'
              : 'Return to your plan and progress, or open the workout studio for a quick session.'}</p>
          </div>
        </div>
        <div className="auth-preview auth-enter" style={{ '--auth-delay': '180ms' } as CSSProperties}>
          <div className="auth-preview-stack">
            <div className="auth-preview-card auth-preview-back"/>
            <div className="auth-preview-card auth-preview-mid"/>
            <div className="auth-preview-float">
              <div className="auth-preview-card auth-preview-front">
                <div className="auth-preview-window">
                  <div className="auth-preview-bar"><span/><span/><span/><b>FITPILOT.</b></div>
                  <div className="auth-preview-body">
                    <aside>
                      <div className="auth-preview-avatar">☺</div>
                      <strong>Your space</strong>
                      <small>A little better, every day</small>
                      <span className="auth-preview-active"><Activity size={12}/>Overview</span>
                      <span><Dumbbell size={12}/>Workouts</span>
                      <span><CalendarDays size={12}/>My week</span>
                    </aside>
                    <div>
                      <span className="auth-preview-label">Make time for</span>
                      <h3>a little you</h3>
                      <div className="auth-preview-stats">
                        <div><small>This week</small><strong>3 workouts</strong></div>
                        <div><small>Time moving</small><strong>75 min</strong></div>
                      </div>
                      <div className="auth-preview-plan">
                        <span>YOUR NEXT SESSION</span>
                        <strong>Build a stronger routine.</strong>
                        <em>Full body · 25 min</em>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="auth-preview-note"><Check size={13}/> Example plan — ready when you are.</div>
              </div>
            </div>
          </div>
        </div>
        <nav className="auth-showcase-trail auth-enter" style={{ '--auth-delay': '320ms' } as CSSProperties}>
          <a href="#/studio">Workout studio</a>
          <span aria-hidden="true">→</span>
          <a href="#features">Weekly plan</a>
          <span aria-hidden="true">→</span>
          <a href="#questions">Progress</a>
        </nav>
        <a className="auth-showcase-support auth-enter" style={{ '--auth-delay': '380ms' } as CSSProperties} href="#questions">Camera stays on your device <ArrowRight size={12}/></a>
      </aside>

      <section className="auth-panel" aria-labelledby="auth-heading">
        <div className="auth-panel-top">
          <a href="#home"><ArrowLeft size={15}/> Back to home</a>
        </div>

        <div className="auth-panel-main">
          <div className="auth-panel-intro">
            <h1 id="auth-heading">{registering ? 'Create your account' : 'Welcome back'}</h1>
            <p>{registering ? 'Set up your FitPilot workspace in a minute.' : 'Sign in to your fitness workspace.'}</p>
          </div>

          <form key={String(registering)} onSubmit={submit} className="auth-form">
            {registering && (
              <label className="auth-field">
                <span>Your name</span>
                <input name="name" autoComplete="name" maxLength={80} placeholder="Enter your name" required/>
              </label>
            )}
            <label className="auth-field">
              <span>Email</span>
              <input name="email" type="email" autoComplete="username" autoCapitalize="none" spellCheck={false} maxLength={254} placeholder="Enter your email" required/>
            </label>
            <label className="auth-field">
              <span>Password</span>
              <span className="auth-password">
                <input name="password" type={showPassword ? 'text' : 'password'} autoComplete={registering ? 'new-password' : 'current-password'} minLength={registering ? 8 : undefined} maxLength={128} placeholder="Enter your password" required aria-describedby={registering ? 'password-hint' : undefined}/>
                <button type="button" className="auth-eye" onClick={() => setShowPassword(v => !v)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                  {showPassword ? <EyeOff size={17}/> : <Eye size={17}/>}
                </button>
              </span>
            </label>
            {registering && <small id="password-hint" className="auth-hint">Use at least 8 characters.</small>}
            {error && <div className="auth-error" role="alert"><span>!</span>{error}</div>}
            <button className="auth-submit" type="submit" disabled={pending}>
              {pending ? 'Please wait…' : registering ? 'Create account' : 'Sign In'} <ArrowRight size={16}/>
            </button>
          </form>

          <p className="auth-switch">
            {registering ? 'Already have an account?' : 'New to FitPilot?'}{' '}
            <button type="button" disabled={pending} onClick={() => { setRegistering(!registering); setError(''); setShowPassword(false) }}>
              {registering ? 'Sign in' : 'Create an account'}
            </button>
          </p>

          <div className="auth-legal">
            <p>Camera video stays on your device. Saving a session sends measurements to FitPilot so your coach can review progress.</p>
          </div>
        </div>

        <footer className="auth-panel-foot">
          <Sparkles size={12}/> Small steps. Your pace.
        </footer>
      </section>
    </main>
  )
}
