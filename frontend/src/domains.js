// domains.js — bridges the Digital Twin's domain vocabulary to the engine's.
//
// Moved here from the hub (modules/simulation/engine/domains.js) per the integration
// plan §0.9: scenarios are domain-scoped, and in the hub the domain comes from whichever
// twin is open. The hub passes `activeDomain` (a TWIN domain key); this file resolves it
// to the engine domain that /scenarios?domain= actually expects.
//
// Note the engine ALSO maps some of these server-side (api/scenarios.py::_DOMAIN_MAP).
// That map is the authority for what runs; this one exists so the UI can tell honestly
// whether a twin has any scenarios at all BEFORE asking, and show the right label.

// Twin domain key -> engine domain. Covers both the hub's own domain ids (mrt-line,
// hospital, ...) and the twin SERVICE's template keys (railway-metro, defence-base, ...):
// a twin opened from "My Twins" carries the service key, one from the library carries the
// hub key, and both must land on the same engine domain.
export const TWIN_DOMAIN_TO_SIM = {
  // railway
  'mrt-line': 'railway',
  'tram-network': 'railway',
  'railway-metro': 'railway',
  'railway-trainset': 'railway',
  'ev-network': 'railway',
  // aerospace / machines
  'turbine-engine': 'aerospace',
  'gas-turbine': 'aerospace',
  'edm-machine': 'aerospace',
  'datacenter': 'aerospace',
  'manufacturing': 'aerospace',
  // hospital
  'hospital': 'hospital',
  'hospital-campus': 'hospital',
  // defence
  'defence-base': 'defence',
  'defence-warship': 'defence',
  'naval-vessel': 'defence',
}

// The engine domain for the active twin, or null if that twin has no engine scenarios.
// Returning null rather than falling back to railway is deliberate: the wrong domain's
// cascade looks plausible and is completely wrong.
export function simDomainForTwin(twinDomain) {
  if (!twinDomain) return null
  return TWIN_DOMAIN_TO_SIM[twinDomain] || TWIN_DOMAIN_TO_SIM[String(twinDomain).toLowerCase()] || null
}

// Operating conditions an operator can stack onto a run.
//
// The engine models operator READINESS, not weather — there is no condition field on
// RunConfig. So a condition applies the way it is actually meaningful: as a readiness
// penalty. That is not cosmetic. Push effective readiness low enough and the root fault's
// containment_rate falls to 0, which fires the engine's "containment_rate < 1" trigger and
// spawns the PREVENTABLE branch. Same scenario, bigger cascade — decided by the engine.
export const CONDITIONS = {
  railway: [
    { id: 'peak', label: 'Peak Hour', penalty: 14 },
    { id: 'reduced_staff', label: 'Reduced Staff', penalty: 12 },
    { id: 'flood', label: 'Flooding', penalty: 12 },
    { id: 'rain', label: 'Heavy Rain', penalty: 10 },
    { id: 'heat', label: 'Heatwave', penalty: 8 },
  ],
  aerospace: [
    { id: 'peak', label: 'Peak Turnaround', penalty: 14 },
    { id: 'reduced_staff', label: 'Reduced Crew', penalty: 12 },
    { id: 'weather', label: 'Adverse Weather', penalty: 12 },
    { id: 'heat', label: 'High OAT', penalty: 8 },
  ],
  hospital: [
    { id: 'surge', label: 'Patient Surge', penalty: 14 },
    { id: 'reduced_staff', label: 'Reduced Staff', penalty: 12 },
    { id: 'heat', label: 'Heatwave', penalty: 8 },
  ],
  defence: [
    { id: 'threat', label: 'Elevated Threat', penalty: 14 },
    { id: 'reduced_staff', label: 'Reduced Manning', penalty: 12 },
    { id: 'weather', label: 'Low Visibility', penalty: 8 },
  ],
}

export const conditionsFor = (domain) => CONDITIONS[domain] || []

// Readiness actually sent to the engine, after condition penalties.
export function effectiveReadiness(domain, readiness, conditionIds = []) {
  const penalty = conditionsFor(domain)
    .filter(c => conditionIds.includes(c.id))
    .reduce((a, c) => a + c.penalty, 0)
  return Math.max(0, Math.min(100, readiness - penalty))
}
