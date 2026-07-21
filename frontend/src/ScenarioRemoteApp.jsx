// ScenarioRemoteApp.jsx — the ONE component the hub mounts.
//
// It wraps ITSELF in its own providers + MemoryRouter + routes, using its OWN module
// instances. The host renders this and nothing else.
//
// Do NOT expose the providers or the router separately for the host to compose — that is
// what produced React #130 ("invalid element type") in the twin integration. One default
// export, self-contained, no exceptions.
//
// No chrome: the hub draws the sidebar and topbar, so the standalone shell in App.jsx
// (sidebar, topbar, domain chooser) is deliberately absent here. No auth gate either —
// the hub owns identity and the gateway injects the engine key server-side.
//
// No BrowserRouter: the hub owns the URL bar, so we navigate in memory.
import React, { useEffect } from 'react'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { StoreProvider } from './store.jsx'
import ScenarioRoutes from './ScenarioRoutes.jsx'
import './styles.css'

// Which page's accent the scoped stylesheet should use. In the standalone shell App.jsx
// puts data-mode on `.app`; embedded there is no `.app`, so it rides the .sc-root wrapper
// (the build scopes `[data-mode=…]` to match the root itself as well as its descendants).
const MODE_FOR = {
  '/dashboard': 'dashboard', '/warroom': 'warroom', '/library': 'library',
  '/builder': 'compose', '/simulation': 'simulation', '/decision': 'decision',
  '/training': 'training', '/twin': 'twin', '/reports': 'reports',
  '/simulate': 'simulate', '/network': 'warroom', '/data': 'data',
  '/ev-network': 'simulation', '/records': 'library', '/assumptions': 'reports',
}

// Keeps the host's sidebar and this remote's router in sync BOTH ways:
//  • host nav changed → `path` prop → navigate here
//  • internal nav here (Builder → Run Simulation → navigate('/simulation')) → report via
//    onNavigate so the host highlights the right sidebar item.
// Without the second half the host stays on "Builder" while Simulation shows, and clicking
// "Builder" does nothing because the host thinks it's already there — the user is trapped.
// That was a real bug in the twin integration; this is its fix.
function RouterBridge({ path, onNavigate, onMode }) {
  const loc = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    if (path && path !== loc.pathname) navigate(path)
  }, [path]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (onNavigate) onNavigate(loc.pathname)
    const key = Object.keys(MODE_FOR).find(p => loc.pathname.startsWith(p))
    onMode(key ? MODE_FOR[key] : 'dashboard')
  }, [loc.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  return null
}

export default function ScenarioRemoteApp({
  initialPath = '/builder',
  path,
  onNavigate,
  activeDomain,     // the hub's active TWIN domain (edm-machine, mrt-line, …)
  activeTwinName,   // display name, for the "which twin am I simulating" banner
}) {
  const [mode, setMode] = React.useState('dashboard')

  return (
    // .sc-root scopes every one of our styles. The hub links this stylesheet into its own
    // <head>, so without this wrapper our rules — `.card`, `.page`, `.panel`, and the bare
    // body/* reset — would restyle the hub's chrome. vite.config.js rewrites every selector
    // in styles.css to sit under .sc-root; this is the element that makes that true.
    <div className="sc-root sc-embedded" data-mode={mode}>
      <MemoryRouter initialEntries={[initialPath]}>
        <StoreProvider twinDomain={activeDomain} twinName={activeTwinName}>
          <RouterBridge path={path} onNavigate={onNavigate} onMode={setMode} />
          <div className="page page-wide">
            <ScenarioRoutes home="/builder" />
          </div>
        </StoreProvider>
      </MemoryRouter>
    </div>
  )
}
