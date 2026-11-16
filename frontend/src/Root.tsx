import { useEffect, useState } from 'react'
import App from './App'
import LandingPage from './LandingPage'

export default function Root() {
  const [route, setRoute] = useState(window.location.hash)
  useEffect(() => {
    const navigate = () => {
      setRoute(window.location.hash)
      if (window.location.hash.startsWith('#/') || !window.location.hash) window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  if (route === '#/app' || route === '#/studio') return <App key={route} initialView={route === '#/studio' ? 'tracker' : 'overview'}/>
  return <LandingPage/>
}
