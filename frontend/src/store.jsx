// store.jsx — one shared state for the whole platform: navigation, the selected domain/
// scenario, the last run, favourites, and the cross-domain scenario library.
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from './api.js'

const Ctx = createContext(null)
export const useStore = () => useContext(Ctx)

const loadFavs = () => { try { return new Set(JSON.parse(localStorage.getItem('simcore_favs') || '[]')) } catch { return new Set() } }

// `twinDomain` / `twinName` are set ONLY when the hub mounts us (ScenarioRemoteApp): in the
// hub the domain comes from the twin you have open, not from our own picker. Standalone
// they are undefined and nothing below changes.
export function StoreProvider({ children, twinDomain, twinName }) {
  const navigate = useNavigate()
  const [engineUp, setEngineUp] = useState(null)

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
  useEffect(() => {
    if (!domains.length) return
    Promise.all(domains.map(async d => {
      const l = await api.scenarios(d.key)
      return (l || []).filter(s => s.node_kind === 'fault').map(s => ({ ...s, domainKey: d.key, domainName: d.name }))
    })).then(lists => setAllScenarios(lists.flat())).catch(() => {})
  }, [domains])

  // Hub-mounted: the ACTIVE TWIN picks the domain. Only if the engine actually has a domain
  // by that name — an unknown twin domain leaves our own selection alone rather than
  // emptying the scenario list and looking like the engine is down.
  useEffect(() => {
    if (!twinDomain || !domains.length) return
    const hit = domains.find(d => d.key === twinDomain) ||
      domains.find(d => twinDomain.startsWith(d.key) || d.key.startsWith(twinDomain))
    if (hit) setDomain(hit.key)
  }, [twinDomain, domains])

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
    twinName,        // hub's active twin, for "which twin am I simulating" banners
    domains, domain, setDomain,
    scenarios, scenarioId, setScenarioId, reloadScenarios: () => loadScenarios(domain),
    allScenarios, favorites, toggleFav, openScenario,
    simSel, setSimSel, builderPick, setBuilderPick, openInBuilder,
    readiness, setReadiness,
    graph, running, error, run,
    mc, mcRunning, runMonteCarlo,
    selected: scenarios.find(s => s.id === scenarioId) || null,
  }), [engineUp, twinName, domains, domain, scenarios, scenarioId, allScenarios, favorites, simSel, builderPick, toggleFav,
    openScenario, openInBuilder, readiness, graph, running, error, run, mc, mcRunning, runMonteCarlo, loadScenarios])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
