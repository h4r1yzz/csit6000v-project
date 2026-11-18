import { useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import { api } from './api'
import BrandMark from './BrandMark'
import './auth.css'

export default function AuthPage({ initialRegister, onSuccess }: { initialRegister: boolean; onSuccess: (registered: boolean) => void }) {
  const [registering, setRegistering] = useState(initialRegister)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

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

  return <main className="auth-page"><section className="auth-card" aria-labelledby="auth-heading">
    <a className="auth-brand" href="#home" aria-label="About FitPilot"><BrandMark size={30}/> FitPilot</a>
    <h1 id="auth-heading">{registering ? 'Create your account' : 'Welcome back'}</h1>
    <p>{registering ? 'Get workout and meal recommendations based on your goals and preferences.' : 'Sign in to see your plan and progress.'}</p>
    <form key={String(registering)} onSubmit={submit}>
      {registering && <label className="field"><span>Your name</span><input name="name" autoComplete="name" maxLength={80} required/></label>}
      <label className="field"><span>Email</span><input name="email" type="email" autoComplete="username" autoCapitalize="none" spellCheck={false} maxLength={254} required/></label>
      <label className="field"><span>Password</span><input name="password" type="password" autoComplete={registering ? 'new-password' : 'current-password'} minLength={registering ? 8 : undefined} maxLength={128} required aria-describedby={registering ? 'password-hint' : undefined}/></label>
      {registering && <small id="password-hint">Use at least 8 characters.</small>}
      {error && <div className="inline-error" role="alert">{error}</div>}
      <button className="primary-button" type="submit" disabled={pending}>{pending ? 'Please wait…' : registering ? 'Create account' : 'Sign in'} <ArrowRight size={16}/></button>
    </form>
    <div className="auth-switch">{registering ? 'Already have an account?' : 'New to FitPilot?'} <button type="button" disabled={pending} onClick={() => { setRegistering(!registering); setError('') }}>{registering ? 'Sign in' : 'Create an account'}</button></div>
  </section></main>
}
