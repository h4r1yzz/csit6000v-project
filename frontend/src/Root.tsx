import { useEffect, useState } from 'react'
import App from './App'
import AuthPage from './AuthPage'
import LandingPage from './LandingPage'
import { api, ApiError } from './api'

type Account = { id: number; email: string; name: string }
const sessionSignal = 'fitpilot-session-changed'

function reloadAfterAuth(hash: string) {
  // Other tabs must discard the previous account's dashboard and drafts too.
  try { localStorage.setItem(sessionSignal, String(Date.now())) } catch { /* Storage may be disabled. */ }
  window.history.replaceState(null, '', window.location.pathname + window.location.search + hash)
  window.location.reload()
}

export default function Root() {
  const [route, setRoute] = useState(window.location.hash)
  const [account, setAccount] = useState<Account | null | undefined>(undefined)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const navigate = () => {
      setRoute(window.location.hash)
      if (window.location.hash.startsWith('#/') || !window.location.hash) window.scrollTo(0, 0)
    }
    const storage = (event: StorageEvent) => { if (event.key === sessionSignal) window.location.reload() }
    const resumed = (event: PageTransitionEvent) => { if (event.persisted) window.location.reload() }
    const expired = () => setAccount(null)
    window.addEventListener('hashchange', navigate)
    window.addEventListener('storage', storage)
    window.addEventListener('pageshow', resumed)
    window.addEventListener('fitpilot-session-expired', expired)
    return () => {
      window.removeEventListener('hashchange', navigate)
      window.removeEventListener('storage', storage)
      window.removeEventListener('pageshow', resumed)
      window.removeEventListener('fitpilot-session-expired', expired)
    }
  }, [])
  useEffect(() => {
    let active = true
    setError('')
    api.get<Account>('/api/auth/me').then(user => {
      if (active) setAccount(user)
    }).catch(ex => {
      if (!active) return
      if (ex instanceof ApiError && ex.status === 401) setAccount(null)
      else setError('Could not reach FitPilot. Check that the backend is running.')
    })
    return () => { active = false }
  }, [attempt])

  if (['#home', '#features', '#how-it-works', '#questions'].includes(route)) return <LandingPage/>
  if (error) return <main className="auth-page"><div className="auth-card"><p role="alert">{error}</p><button className="quiet-button" onClick={() => setAttempt(v => v + 1)}>Retry</button></div></main>
  if (account === undefined) return <main className="auth-page" role="status">Opening FitPilot…</main>
  if (!account) return <AuthPage initialRegister={route !== '#/login'} onSuccess={registered => reloadAfterAuth(registered ? '#/preferences' : route === '#/login' ? '#/app' : route)}/>
  const view = route === '#/studio' ? 'tracker' : route === '#/preferences' ? 'profile' : 'overview'
  return <App key={account.id + '-' + view} initialView={view} onLogout={async () => {
    await api.post('/api/auth/logout', {})
    reloadAfterAuth('#/login')
  }}/>
}
