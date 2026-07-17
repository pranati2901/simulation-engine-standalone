// ScenarioRemoteApp.jsx — the ONE component the hub mounts (integration plan §0.2).
//
// It wraps ITSELF in its own providers + MemoryRouter + routes, using its OWN module
// instances. The host renders this and nothing else.
//
// Do NOT expose the providers or the router separately for the host to compose — that is
// what produced React #130 ("invalid element type") in the twin integration. One default
// export, self-contained, no exceptions.
//
// No chrome: the hub draws the sidebar and topbar. No auth gate: the hub owns identity.
// No BrowserRouter: the hub owns the URL bar, so we navigate in memory.
import React, { useEffect } from 'react'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { StoreProvider } from './store.jsx'
import ScenarioRoutes from './ScenarioRoutes.jsx'
import './styles.css'

// Keeps the host's sidebar and this remote's router in sync BOTH ways:
//  • host nav changed → `path` prop → navigate here
//  • internal nav here (Builder → Run Simulation → navigate('/simulation')) → report via
//    onNavigate so the host highlights the right sidebar item.
// Without the second half the host stays on "Builder" while Simulation shows, and clicking
// "Builder" does nothing because the host thinks it's already there — the user is trapped.
// That was a real bug in the twin integration; this is its fix, copied verbatim.
function RouterBridge({ path, onNavigate }) {
  const loc = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    if (path && path !== loc.pathname) navigate(path)
  }, [path]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (onNavigate) onNavigate(loc.pathname)
  }, [loc.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  return null
}

export default function ScenarioRemoteApp({
  initialPath = '/builder',
  path,
  onNavigate,
  activeDomain,     // the hub's active TWIN domain (edm-machine, mrt-line, …) — §0.9
  activeTwinName,   // display name, for the "which twin am I simulating" banner
}) {
  return (
    // .sc-root scopes every one of our styles. The hub links this stylesheet into its own
    // <head>, so without this wrapper our rules would restyle the hub's chrome (§0.8).
    <div className="sc-root sc-embedded">
      <MemoryRouter initialEntries={[initialPath]}>
        <StoreProvider twinDomain={activeDomain} twinName={activeTwinName}>
          <RouterBridge path={path} onNavigate={onNavigate} />
          <div className="page">
            <ScenarioRoutes />
          </div>
        </StoreProvider>
      </MemoryRouter>
    </div>
  )
}
