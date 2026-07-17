// store.jsx — one shared state for the whole platform: navigation, the selected domain/
// scenario, the last run, favourites, and the cross-domain scenario library.
//
// `twinDomain` / `twinName` are supplied by the HUB when this app runs as a federated
// remote: scenarios are domain-scoped and in the hub the domain comes from whichever twin
// is open (integration plan §0.9). Standalone they are undefined and the pages fall back
// to their own pickers, so every vertical stays reachable without a twin.
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from './api.js'
import { simDomainForTwin } from './domains.js'

const Ctx = createContext(null)
export const useStore = () => useContext(Ctx)

const loadFavs = () => { try { return new Set(JSON.parse(localStorage.getItem('simcore_favs') || '[]')) } catch { return new Set() } }

export function StoreProvider({ children, twinDomain, twinName }) {
  const navigate = useNavigate()
  const [engineUp, setEngineUp] = useState(null)

  // The engine domain the hub's active twin maps to, or null if that twin has no engine
  // scenarios. Null rather than a default is deliberate — showing another domain's cascade
  // for this twin would look plausible and be completely wrong.
  const activeDomain = useMemo(() => simDomainForTwin(twinDomain), [twinDomain])

  const [domains, setDomains] = useState([])
  const [domain, setDomain] = useState('')
  const [scenarios, setScenarios] = useState([])
  const [scenarioId, setScenarioId] = useState('')
  const [readiness, setReadiness] = useState(55)

  const [allScenarios, setAllScenarios] = useState([])   // every fault across every domain
  const [favorites, setFavorites] = useState(loadFavs)
  const [simSel, setSimSel] = useState(null)             // Builder → Simulation hand-off
  const [builderPick, setBuilderPick] = useState(null)   // Library → Builder hand-off

  const [graph, setGraph] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [mc, setMc] = useState(null)
  const [mcRunning, setMcRunning] = useState(false)

  const pendingRef = useRef(null)   // a scenario id to select once its domain's list loads

  useEffect(() => {
    api.domains()
      .then(ds => { setEngineUp(true); setDomains(ds); setDomain(d => d || ds[0]?.key || '') })
      .catch(e => { setEngineUp(false); setError(e.message) })
  }, [])

  // cross-domain library
  const reloadAll = useCallback(async () => {
    if (!domains.length) return
    const lists = await Promise.all(domains.map(async d => {
      const l = await api.scenarios(d.key)
      return (l || []).filter(s => s.node_kind === 'fault').map(s => ({ ...s, domainKey: d.key, domainName: d.name }))
    }))
    setAllScenarios(lists.flat())
  }, [domains])
  useEffect(() => { reloadAll().catch(() => {}) }, [reloadAll])

  // Follow the hub's twin. Only when that twin actually HAS an engine domain — otherwise
  // keep whatever is selected rather than switching to something unrelated.
  useEffect(() => { if (activeDomain) setDomain(activeDomain) }, [activeDomain])

  const loadScenarios = useCallback(async (d) => {
    const list = await api.scenarios(d)
    const faults = (list || []).filter(s => s.node_kind === 'fault')
    setScenarios(faults)
    const want = pendingRef.current; pendingRef.current = null
    setScenarioId(prev => (want && faults.some(f => f.id === want)) ? want
      : (faults.some(f => f.id === prev) ? prev : (faults[0]?.id || '')))
    return faults
  }, [])

  useEffect(() => {
    if (!domain) return
    setGraph(null); setMc(null); setError(null)
    loadScenarios(domain).catch(e => setError(e.message))
  }, [domain, loadScenarios])

  const run = useCallback(async () => {
    if (!scenarioId) return
    setRunning(true); setError(null); setMc(null)
    try { setGraph(await api.runGraph(scenarioId, domain, readiness)) }
    catch (e) { setError(e.message); setGraph(null) }
    finally { setRunning(false) }
  }, [scenarioId, domain, readiness])

  const runMonteCarlo = useCallback(async () => {
    if (!scenarioId) return
    setMcRunning(true); setError(null)
    try { setMc(await api.monteCarlo(scenarioId, domain)) }
    catch (e) { setError(e.message) } finally { setMcRunning(false) }
  }, [scenarioId, domain])

  // open a scenario from anywhere (library, dashboard) → jump into Decision mode
  const openScenario = useCallback((dk, id) => {
    navigate('/decision')
    if (dk === domain) setScenarioId(id)
    else { pendingRef.current = id; setDomain(dk) }
  }, [domain, navigate])

  // open a scenario straight into the Builder (used by the Library)
  const openInBuilder = useCallback((dk, id) => {
    setBuilderPick({ domainKey: dk, id }); navigate('/builder')
  }, [navigate])

  const toggleFav = useCallback((id) => {
    setFavorites(prev => {
      const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id)
      localStorage.setItem('simcore_favs', JSON.stringify([...n])); return n
    })
  }, [])

  const value = useMemo(() => ({
    engineUp,
    domains, domain, setDomain,
    activeDomain, activeTwinName: twinName || null,
    scenarios, scenarioId, setScenarioId, reloadScenarios: () => loadScenarios(domain),
    allScenarios, reloadAll, favorites, toggleFav, openScenario,
    simSel, setSimSel, builderPick, setBuilderPick, openInBuilder,
    readiness, setReadiness,
    graph, running, error, run,
    mc, mcRunning, runMonteCarlo,
    selected: scenarios.find(s => s.id === scenarioId) || null,
  }), [engineUp, domains, domain, activeDomain, twinName, scenarios, scenarioId, allScenarios, reloadAll, favorites,
    simSel, builderPick, toggleFav, openScenario, openInBuilder, readiness, graph, running, error, run,
    mc, mcRunning, runMonteCarlo, loadScenarios])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
