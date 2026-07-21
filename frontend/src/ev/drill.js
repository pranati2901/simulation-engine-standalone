// drill.js — the "Take Command" interactive incident-response playbook. For any (asset, fault)
// it yields an ORDERED procedure of richly-detailed, interactive steps. Each step reacts on the
// live 3-D twin: diagnosing reads a real signal, actions push telemetry back toward healthy,
// safety gates protect equipment, and doing things out of order re-trips the fault.
//
// A step:
//   id, title, icon, kind: 'diagnose'|'action'|'verify'
//   brief     — one-line subtitle
//   detail    — what you're doing and WHY (paragraph)
//   mechanism — how it actually works (the engineering)
//   targets   — ev: signals it reads/affects (shown as live readouts on the card)
//   requires  — [stepId] prerequisites; acting early = order violation + re-trip
//   safety    — true → a confirm-gesture gate; skipping it is a safety violation
//   confirm   — label for the safety/critical confirm checkbox
//   w         — containment weight (0..1): how much closer to stable this gets you
//   cost      — response cost as a fraction of full exposure (0..1)
//   seconds   — how long the action takes to execute (clock keeps ticking)
//   effect    — { 'ev:signal': delta } applied over `seconds`; omit for a generic heal by w
//   choose    — { prompt, options:[{label, mult, cost, note}] } a level decision that scales effect
//   diagnose  — { prompt, options:[{signal,label,right}] } identify the fault from the twin
//   verifyWhen— predicate name: 'stable' (verify only valid once the site is stable)
//   risk      — consequence line shown if skipped / done out of order
import { HEALTHY, strategiesFor } from './scenarios.js'

// ── the "worse" cap each signal drifts toward if you do nothing, and its worse direction ──
export const CAP = {
  'ev:gridLoad': 108, 'ev:transformerTemp': 100, 'ev:thermalRunawayRisk': 92, 'ev:cellTempMax': 52,
  'ev:faultedChargers': 10, 'ev:peakDemand': 760, 'ev:loadHeadroom': 0, 'ev:bessSoc': 4,
  'ev:chargingPower': 0, 'ev:sessionsActive': 0, 'ev:bessPower': 0, 'ev:solarOutput': 0,
}

// ── bespoke, high-detail procedures for the demo hotspots ──
const P = {
  'TX-1:overload': {
    objective: 'Hold Transformer T1 below 90% load and stop the DC bank tripping — before the protection relay hard-trips the whole site.',
    steps: [
      { id: 'diag', title: 'Localise the overload', icon: '🔎', kind: 'diagnose', w: 0.05, seconds: 3,
        brief: 'Read the twin and confirm what is actually failing.',
        detail: 'Before you touch anything, confirm the fault is a real transformer overload and not a downstream trip. The digital twin is showing you every live signal — find the one that is out of band.',
        mechanism: 'Transformer loading = drawn kVA ÷ nameplate kVA. Above ~90% the top-oil temperature climbs and the Buchholz/overcurrent protection arms.',
        targets: ['ev:gridLoad', 'ev:transformerTemp', 'ev:loadHeadroom'],
        diagnose: { prompt: 'Which reading is driving this incident?', options: [
          { signal: 'ev:gridLoad', label: 'Transformer load %', right: true },
          { signal: 'ev:solarOutput', label: 'Solar output kW' },
          { signal: 'ev:sessionsActive', label: 'Active sessions' },
        ] },
        risk: 'Acting blind — you may shed the wrong load and never fix the overload.' },
      { id: 'shed', title: 'Shed non-critical DC load', icon: '✂️', kind: 'action', requires: ['diag'], w: 0.34, cost: 0.06, seconds: 6,
        brief: 'Drop low-priority DC sessions to pull load off T1 immediately.',
        detail: 'The fastest lever you own. Curtailing the lowest-priority DC-fast sessions instantly reduces the kVA on the transformer. Shed more and you contain harder — but you drop more paying sessions.',
        mechanism: 'EMS sends OCPP SetChargingProfile at 0 kW to the lowest-priority EVSEs; their load leaves T1 within one control cycle.',
        targets: ['ev:gridLoad', 'ev:chargingPower', 'ev:sessionsActive'],
        choose: { prompt: 'How much DC load do you shed?', options: [
          { label: 'Shed 30% — gentle', mult: 0.55, cost: 0.03, note: 'keeps most sessions, softer relief' },
          { label: 'Shed 50% — balanced', mult: 1.0, cost: 0.06, note: 'the textbook move' },
          { label: 'Shed 70% — aggressive', mult: 1.35, cost: 0.11, note: 'max relief, drops many sessions' },
        ] },
        effect: { 'ev:gridLoad': -16, 'ev:transformerTemp': -6, 'ev:chargingPower': -140, 'ev:loadHeadroom': 12 },
        risk: 'Left unshed, T1 keeps climbing and the relay hard-trips every charger.' },
      { id: 'bess', title: 'Dispatch BESS-A to cover the peak', icon: '🔋', kind: 'action', requires: ['diag'], w: 0.34, cost: 0.05, seconds: 6, safety: true,
        confirm: 'Confirmed: BESS-A SoC > 25% and no thermal flag — safe to discharge',
        brief: 'Discharge on-site storage so the grid draw on T1 drops.',
        detail: 'BESS-A can carry the peak so the transformer does not have to. This is the highest-value move because it cuts load without dropping a single session — but you must confirm the pack is healthy before you command a hard discharge.',
        mechanism: 'The EMS commands BESS-A to discharge at up to its inverter limit; that power offsets grid import 1:1, so T1 loading falls by the dispatched kW.',
        targets: ['ev:gridLoad', 'ev:bessPower', 'ev:bessSoc'],
        choose: { prompt: 'Dispatch level?', options: [
          { label: '50% — conserve SoC', mult: 0.6, cost: 0.03, note: 'saves reserve for later' },
          { label: '80% — recommended', mult: 1.0, cost: 0.05, note: 'strong peak cover' },
          { label: '100% — everything', mult: 1.25, cost: 0.08, note: 'max cover, drains the pack' },
        ] },
        effect: { 'ev:gridLoad': -14, 'ev:transformerTemp': -5, 'ev:bessPower': 70, 'ev:bessSoc': -18, 'ev:loadHeadroom': 10 },
        risk: 'Discharging a low or hot pack can push BESS-A itself into a thermal event.' },
      { id: 'verify', title: 'Confirm T1 stable & release', icon: '✅', kind: 'verify', requires: ['shed'], w: 0.05, seconds: 3, verifyWhen: 'stable',
        brief: 'Verify the transformer is back under 90% before you sign off.',
        detail: 'Do not close the incident until the twin proves it. Confirm load and top-oil temperature are back in band, then hand control back to normal EMS scheduling.',
        mechanism: 'You are checking the same signals you diagnosed with — load < 90%, headroom recovered, temperature falling — the objective is met only when they hold.',
        targets: ['ev:gridLoad', 'ev:loadHeadroom', 'ev:transformerTemp'],
        risk: 'Signing off while still overloaded is a false all-clear — the fault re-develops unattended.' },
    ],
  },

  'BESS-A:thermal_runaway': {
    objective: 'Stop BESS-A going into thermal runaway (fire), then carry the load it was covering — without spiking the demand charge.',
    steps: [
      { id: 'diag', title: 'Confirm the thermal event', icon: '🔎', kind: 'diagnose', w: 0.05, seconds: 3,
        brief: 'Identify the runaway precursor on the pack.',
        detail: 'A cell venting looks like many things. Confirm it is a genuine thermal-runaway precursor — rising cell temperature and runaway-risk index — not just a warm afternoon.',
        mechanism: 'BMS reports max cell temperature and dV/dt per cell. A runaway precursor is a sharp cell-temp rise with off-gassing; the risk index fuses both.',
        targets: ['ev:thermalRunawayRisk', 'ev:cellTempMax', 'ev:bessSoc'],
        diagnose: { prompt: 'Which signal confirms a runaway precursor?', options: [
          { signal: 'ev:thermalRunawayRisk', label: 'Thermal-runaway risk %', right: true },
          { signal: 'ev:gridLoad', label: 'Transformer load %' },
          { signal: 'ev:solarOutput', label: 'Solar output kW' },
        ] },
        risk: 'Misreading a runaway as a nuisance alarm costs you the only minutes that matter.' },
      { id: 'isolate', title: 'Isolate & cool the pack', icon: '🧯', kind: 'action', requires: ['diag'], w: 0.5, cost: 0.03, seconds: 7, safety: true,
        confirm: 'Confirmed: personnel clear of the BESS enclosure — arming suppression',
        brief: 'Open the DC contactors and trigger liquid cooling + suppression.',
        detail: 'The single most important action. Electrically isolate BESS-A so no current feeds the hot cells, then dump coolant and arm the suppression system to pull heat out before propagation. Confirm nobody is at the enclosure first.',
        mechanism: 'Opening the pack contactors removes charge/discharge current; the liquid-cooling loop and aerosol suppression drop cell temperature below the self-heating threshold, halting the exotherm.',
        targets: ['ev:thermalRunawayRisk', 'ev:cellTempMax', 'ev:bessPower'],
        effect: { 'ev:thermalRunawayRisk': -40, 'ev:cellTempMax': -14, 'ev:bessPower': -80 },
        risk: 'Every second unisolated, current keeps feeding the exotherm — this cannot wait behind anything.' },
      { id: 'cover', title: 'Cover the load from grid', icon: '🔌', kind: 'action', requires: ['isolate'], w: 0.28, cost: 0.09, seconds: 6,
        brief: 'Pick up the load BESS-A was carrying — inside the demand-charge cap.',
        detail: 'With BESS-A offline, the peak it was shaving now hits the grid. Import to cover it, but choose how hard: too much grid import trips a costly demand-charge ratchet.',
        mechanism: 'Demand charge bills on the monthly kW peak. You raise grid import to serve load, trading energy cost against the SLA of keeping chargers up.',
        targets: ['ev:gridLoad', 'ev:loadHeadroom', 'ev:peakDemand'],
        choose: { prompt: 'How much grid do you pull?', options: [
          { label: 'Cap at demand limit', mult: 0.7, cost: 0.05, note: 'protects the demand charge, sheds some DC' },
          { label: 'Full cover', mult: 1.0, cost: 0.09, note: 'keeps everything up, risks the ratchet' },
        ] },
        effect: { 'ev:gridLoad': 6, 'ev:loadHeadroom': -4, 'ev:peakDemand': 40, 'ev:faultedChargers': -1 },
        isRecovery: true,
        risk: 'No cover and the chargers BESS-A was supporting drop offline.' },
      { id: 'verify', title: 'Confirm safe & load served', icon: '✅', kind: 'verify', requires: ['isolate'], w: 0.05, seconds: 3, verifyWhen: 'stable',
        brief: 'Verify runaway risk is neutralised and load is served.',
        detail: 'Close the incident only when the runaway-risk index has collapsed and the load BESS-A was carrying is covered. Log the pack for post-incident inspection.',
        mechanism: 'Runaway risk back near baseline and cell temperature falling proves the exotherm is arrested; load served proves the grid pickup worked.',
        targets: ['ev:thermalRunawayRisk', 'ev:cellTempMax', 'ev:faultedChargers'],
        risk: 'A premature all-clear on a hot pack is how re-ignition happens.' },
    ],
  },

  'DCFC:charger_offline': {
    objective: 'Get the offline DC-fast chargers earning again — cheapest path first, truck-roll only if you must.',
    steps: [
      { id: 'diag', title: 'Triage the offline bank', icon: '🔎', kind: 'diagnose', w: 0.05, seconds: 3,
        brief: 'Confirm it is a controller/comms fault, not a power fault.',
        detail: 'Offline chargers with healthy upstream power almost always means the OCPP session controller has wedged. Confirm the chargers are the anomaly, not the feeder behind them.',
        mechanism: 'A charger that lost its OCPP WebSocket shows "offline" to the CPMS while its EVSE and feeder are perfectly healthy — a soft fault, remotely fixable.',
        targets: ['ev:faultedChargers', 'ev:sessionsActive', 'ev:gridLoad'],
        diagnose: { prompt: 'What is actually abnormal?', options: [
          { signal: 'ev:faultedChargers', label: 'Faulted chargers', right: true },
          { signal: 'ev:transformerTemp', label: 'Transformer temp' },
          { signal: 'ev:bessSoc', label: 'BESS state of charge' },
        ] },
        risk: 'Truck-rolling a fault that a remote reboot would clear burns hours and money.' },
      { id: 'reboot', title: 'Remote-reboot the OCPP controller', icon: '🔁', kind: 'action', requires: ['diag'], w: 0.5, cost: 0.01, seconds: 5,
        brief: 'The cheapest fix — restart the session controller over the wire.',
        detail: 'Send a soft reset to the wedged charge-point controllers. This clears the vast majority of "offline" faults in seconds at effectively zero cost, and no truck moves.',
        mechanism: 'A Reset[soft] over OCPP re-establishes the WebSocket and reloads the session state machine; the EVSE re-registers and comes back Available.',
        targets: ['ev:faultedChargers', 'ev:sessionsActive'],
        effect: { 'ev:faultedChargers': -2, 'ev:sessionsActive': 3, 'ev:chargingPower': 80 },
        risk: 'Skipping the free fix and rerouting drivers loses sessions you could have kept.' },
      { id: 'reroute', title: 'Reroute waiting drivers', icon: '🧭', kind: 'action', requires: ['diag'], w: 0.22, cost: 0.03, seconds: 4,
        brief: 'Send arriving EVs to working bays so nobody waits at a dead charger.',
        detail: 'While the reboot lands, keep customers charging by steering them to healthy bays through the app — protects the customer experience and recovers session revenue.',
        mechanism: 'The driver app repoints navigation to Available EVSEs at the same site; queueing shifts off the offline bank.',
        targets: ['ev:sessionsActive', 'ev:faultedChargers'],
        effect: { 'ev:sessionsActive': 2, 'ev:faultedChargers': -1 },
        risk: 'Drivers stack up at dead bays, abandon the site, and you lose the sessions entirely.' },
      { id: 'truck', title: 'Dispatch a truck-roll (last resort)', icon: '🚚', kind: 'action', requires: ['reboot'], w: 0.18, cost: 0.09, seconds: 6,
        brief: 'Only if the reboot did not clear it — send a technician.',
        detail: 'If the controller stays offline after a reboot, it is a hardware fault. Dispatch a field technician — the slowest, most expensive lever, justified only once the cheap fixes fail.',
        mechanism: 'A tech power-cycles the unit, checks the AC input and comms module, and swaps the controller board if needed.',
        targets: ['ev:faultedChargers', 'ev:sessionsActive'],
        effect: { 'ev:faultedChargers': -1, 'ev:sessionsActive': 1 },
        risk: 'Dispatching before trying the reboot wastes a truck on a two-second software fix.' },
      { id: 'verify', title: 'Confirm bank restored', icon: '✅', kind: 'verify', requires: ['reboot'], w: 0.05, seconds: 3, verifyWhen: 'stable',
        brief: 'Verify chargers are Available and sessions are flowing.',
        detail: 'Close the ticket when faulted-charger count is back to zero and sessions are live again on the recovered bays.',
        mechanism: 'Faulted count at zero and active sessions climbing confirms the EVSEs re-registered and are dispensing energy.',
        targets: ['ev:faultedChargers', 'ev:sessionsActive'],
        risk: 'Closing early hides a charger still stuck offline and quietly bleeding revenue.' },
    ],
  },
}

// ── PHASE 2: the field-repair procedure (hardware fix) — runs AFTER the site is stabilised.
// Technician workflow: make-safe → inspect → replace → recalibrate → test → sign off.
// Order + lockout are enforced; `heal` is how much asset health each step restores.
export function repairStepsFor(assetName, faultName) {
  return [
    { id: 'loto', title: 'Isolate & lock out (LOTO)', icon: '🔒', kind: 'safety', safety: true, heal: 0.06,
      brief: 'De-energise the asset and prove zero energy before touching hardware.',
      detail: `Apply lockout/tagout on ${assetName} and verify zero energy at the point of work. Nothing physical happens until this is confirmed.`,
      mechanism: 'Breaker locked open and tagged, stored energy discharged, absence-of-voltage tested — the legal and physical precondition for any hands-on work.',
      howto: [`Identify the upstream isolation point / breaker for ${assetName}`, 'Open the breaker, apply your personal lock and tag', 'Discharge any stored energy (caps / DC bus / the pack)', 'Test for absence of voltage — prove it is dead'],
      risk: 'Working a live asset is the #1 cause of arc-flash and electrocution — an automatic fail.' },
    { id: 'inspect', title: 'Inspect the failed component', icon: '🔎', kind: 'action', physical: true, requires: ['loto'], heal: 0.15,
      brief: `Open the enclosure and confirm the failure mode on ${assetName}.`,
      detail: `Confirm the root cause with eyes-on inspection before swapping anything — thermal damage, a tripped device, a failed connector, a seized pump.`,
      mechanism: 'Visual + thermal-camera inspection localises the failed element so you replace the actual fault, not a symptom.',
      howto: ['Open the enclosure / access panel', 'Do a visual + thermal-camera scan of the suspect area', 'Localise the failed element (burnt, tripped, seized)', 'Record the failure mode before removing anything'],
      risk: 'Skip inspection and you may replace a healthy part while the real fault stays in service.' },
    { id: 'replace', title: 'Repair / replace the part', icon: '🔧', kind: 'action', physical: true, requires: ['inspect'], heal: 0.32,
      brief: 'Restore or swap the failed component to serviceable spec.',
      detail: 'Replace the failed element (contactor, connector, cooling pump, cell module) with a serviceable unit to the OEM specification.',
      mechanism: 'Correct part number, torqued to spec, terminations verified — this is what actually restores the asset’s designed capability.',
      howto: ['Confirm the correct OEM part number', 'Remove the failed component', 'Fit the replacement and torque to spec', 'Verify all terminations are tight and correct'],
      risk: 'A wrong or mis-torqued part re-fails under load, usually worse than the original fault.' },
    { id: 'recal', title: 'Recalibrate to spec', icon: '🎚', kind: 'action', physical: true, requires: ['replace'], heal: 0.18,
      brief: 'Reload set-points and protection thresholds.',
      detail: 'Re-reference set-points, protection thresholds and calibration so the asset behaves exactly to design.',
      mechanism: 'Protection relays, BMS limits and controller set-points are re-loaded and verified against the spec sheet.',
      howto: ['Open the controller / protection config', 'Load the set-points from the spec sheet', 'Set protection thresholds / BMS limits', 'Re-reference calibration and verify against spec'],
      risk: 'Wrong thresholds either nuisance-trip the asset or fail to protect it.' },
    { id: 'test', title: 'Functional test under load', icon: '⚡', kind: 'action', requires: ['recal'], heal: 0.22,
      brief: 'Re-energise and confirm the asset holds nominal under load.',
      detail: 'Remove LOTO, re-energise and run the asset up under load to confirm it holds nominal readings — not just at idle.',
      mechanism: 'Staged re-energisation with live telemetry watched against the healthy envelope proves the repair holds.',
      howto: ['Remove your lock/tag (LOTO)', 'Re-energise in stages, watching for faults', 'Run the asset up under load', 'Watch live telemetry hold nominal across the envelope'],
      risk: 'Signing off without a load test hides a repair that only works unloaded.' },
    { id: 'signoff', title: 'Verify health & close work order', icon: '✅', kind: 'verify', verify: true, requires: ['test'], heal: 0.07,
      brief: 'Confirm full health and close the job.',
      detail: `Confirm ${assetName} reads healthy across the board and close the work order with the repair logged for audit.`,
      mechanism: 'Health restored + telemetry in-band + work order logged = an auditable, defensible closure.',
      howto: [`Confirm ${assetName} reads healthy across all signals`, 'Confirm telemetry is back in-band and stable', 'Log the repair, parts used and readings', 'Close the work order'],
      risk: 'Close early and an unverified repair goes back into service.' },
  ]
}

// which 3-D twin asset each bespoke step is working on → the scene highlights it as you go
const STEP_FOCUS = {
  'TX-1:overload': { diag: 'TX-1', shed: 'DCFC-01', bess: 'BESS-A', verify: 'TX-1' },
  'BESS-A:thermal_runaway': { diag: 'BESS-A', isolate: 'BESS-A', cover: 'TX-1', verify: 'BESS-A' },
  'DCFC:charger_offline': { diag: 'DCFC-01', reboot: 'DCFC-01', reroute: 'DCFC-01', truck: 'DCFC-01', verify: 'DCFC-01' },
}

// The concrete "HOW" for each bespoke step — the actual operator procedure a trainee performs.
// This is what turns the drill from "click Execute" into "learn how to shed load, step by step".
const HOWTO = {
  'TX-1:overload': {
    diag: ['Open the EMS dashboard → Transformer T1 panel', 'Compare live load % against the 90% protection threshold', 'Confirm top-oil temperature is rising (a real overload, not a downstream trip)', 'Note the headroom left before the relay arms'],
    shed: ['Open EMS → Load Management → DC chargers', 'Sort active sessions by priority (lowest first)', 'Select the low-priority DC sessions to curtail', 'Send OCPP SetChargingProfile = 0 kW to those EVSEs', 'Watch Transformer T1 load drop back under 90%'],
    bess: ['Check BESS-A SoC > 25% and no thermal flag', 'Open EMS → Storage → BESS-A → set mode = Discharge', 'Set target = peak-shave and ramp to the chosen level', 'Confirm grid import (and T1 load) falls by the dispatched kW'],
    verify: ['Read Transformer T1 load — confirm it holds < 90%', 'Confirm headroom recovered and temperature falling', 'Hand control back to normal EMS scheduling', 'Log the incident and close'],
  },
  'BESS-A:thermal_runaway': {
    diag: ['Open the BMS → BESS-A cell view', 'Check the max cell-temperature trend (rising fast?)', 'Read the runaway-risk index vs its baseline', 'Rule out a nuisance / ambient-heat alarm'],
    isolate: ['Confirm all personnel are clear of the enclosure', 'Open the BESS-A DC contactors to electrically isolate the pack', 'Trigger the liquid-cooling loop', 'Arm the aerosol suppression system', 'Watch runaway-risk and cell temperature fall'],
    cover: ['Open EMS → Grid import and read the demand-charge ceiling', 'Raise grid import to serve the load BESS-A was covering', 'Cap import at the demand limit to protect the ratchet', 'Confirm the affected chargers stay up'],
    verify: ['Confirm runaway risk is back near baseline', 'Confirm cell temperature is falling', 'Confirm the load is served / chargers restored', 'Flag BESS-A for post-incident inspection'],
  },
  'DCFC:charger_offline': {
    diag: ['Open the CPMS → charger status board', 'Confirm the bank shows "offline" (comms), not a power fault', 'Check the feeder behind them is healthy', 'Conclude it is a controller / OCPP fault'],
    reboot: ['Select the offline charge points in the CPMS', 'Send OCPP Reset[soft] to them', 'Wait for the WebSocket to re-establish', 'Confirm the EVSEs re-register as Available'],
    reroute: ['Open the driver app / signage controller', 'Mark the offline bays unavailable', 'Repoint arriving drivers to the healthy bays'],
    truck: ['Confirm the reboot did NOT clear the fault', 'Raise a field work order', 'Dispatch a technician with a spare controller board', 'Track the ETA and keep drivers informed'],
    verify: ['Confirm faulted-charger count is back to 0', 'Confirm sessions are flowing on the recovered bays', 'Close the ticket'],
  },
}
const GENERIC_HOWTO = {
  diagnose: ['Open the digital twin → the affected asset and read its live tags', 'Find the signal sitting outside its healthy band (load, temp, risk, faulted count)', 'Cross-check the trend — rising, or a one-off spike?', 'Confirm it matches the reported fault before you commit a response'],
  verify: ['Re-read the signals you diagnosed — confirm they are back in-band', 'Confirm the response is holding, not just momentarily better', 'Return the asset to normal control', 'Log the cause, actions and outcome, then close'],
}

// The concrete operator procedure for EACH response lever, keyed by strategy id. This deepens
// the how-to for EVERY fault (not just the bespoke three) — feeder trips, connector faults,
// grid brownout/supply-loss, BESS offline, transformer overheat all get real, specific steps.
const STRAT_HOWTO = {
  shed: ['EMS → Load Management → DC chargers, sort by session priority', 'Tag the lowest-priority DC sessions (idle / fleet first)', 'Send OCPP SetChargingProfile: chargingRateUnit=W, limit=0', 'Confirm those EVSEs report SuspendedEVSE', 'Watch the transformer load fall back in-band (~2–5 s)'],
  bess: ['Confirm BESS-A SoC > 25% and no thermal flag on the BMS', 'EMS → Storage → BESS-A → Mode = Discharge (peak-shave)', 'Setpoint kW = (grid import − the limit); ramp up', 'Confirm grid import drops ~1:1 with BESS output', 'Hold until the asset is back in band'],
  curtail: ['EMS → Load Management → global DC power cap', 'Set the site DC cap to ~50% of nameplate', 'Push SetChargingProfile at the cap to all DC EVSEs', 'Confirm total DC-fast kW halves and the fault eases'],
  cool: ['SCADA → Transformer T1 → Cooling = Forced (fans + oil pumps ON)', 'EMS → throttle DC-fast power 20–30%', 'Watch the top-oil temperature (tag TX1.OILTEMP) stop climbing', 'Hold until temp trends below the derate threshold'],
  shift: ['EMS → Feeder balance view; read both feeders’ headroom', 'Confirm the target feeder headroom > the load you’ll move', 'Reassign the DC bank / AC bays to the healthy feeder', 'Confirm both feeders sit under their limit — no overcurrent'],
  reclose: ['Confirm the overcurrent cause is cleared / load already shed', 'SCADA → Feeder → reset the relay lockout', 'Issue the Close command', 'Watch current settle — no immediate re-trip'],
  rebal: ['EMS → move the DC bank source onto Feeder F-2', 'Confirm F-2 headroom covers the bank load', 'Restore charging on the rebalanced bank', 'Confirm neither feeder exceeds its limit'],
  stagger: ['EMS → AC bays → enable session sequencing', 'Set max concurrent AC sessions under the feeder limit', 'Queue the remaining sessions', 'Confirm feeder current stays below the trip point'],
  reboot: ['CPMS → select the offline charge points', 'Send OCPP Reset: type=Soft', 'Wait ~30 s for the WebSocket + BootNotification', 'Confirm each EVSE re-registers as Available', 'Fire a test StartTransaction to confirm it dispenses'],
  reroute: ['Open the driver app / on-site signage controller', 'Set the offline bays to Unavailable', 'Repoint navigation + queue to the healthy bays', 'Confirm arrivals stop stacking at the dead bays'],
  truck: ['Confirm the reboot did NOT restore the unit (hardware fault)', 'Raise a field work order and attach the diagnostic log', 'Dispatch a tech with a spare controller / comms board', 'Track the ETA and keep drivers informed via the app'],
  lock: ['CPMS → the faulted connector → set Unavailable / Locked', 'Confirm no session can start on it', 'Route the waiting driver to the adjacent bay', 'Raise a repair ticket for the connector'],
  reset: ['CPMS → connector → run remote diagnostics', 'Clear the logged fault code', 'Send a soft reset to the EVSE', 'Confirm the connector returns to Available'],
  isolate: ['Confirm all personnel are clear of the BESS enclosure', 'Command Open on the BESS-A DC contactors (electrical isolation)', 'Start the liquid-cooling loop at max flow', 'Arm the aerosol / clean-agent suppression', 'Watch runaway-risk and max cell temp fall'],
  gridcov: ['EMS → Grid import; read the monthly demand-charge ceiling', 'Raise import to cover the kW the pack was shaving', 'Cap import at the demand limit to avoid the ratchet', 'Confirm the affected chargers stay online'],
  hold: ['EMS → set the grid as the primary source', 'Check the demand-charge headroom', 'Carry the peak within the cap', 'Shed low-priority DC if you approach the ratchet'],
  backup: ['Start the backup storage / genset', 'Sync it to the bus', 'Transfer load onto the backup', 'Confirm site support is restored'],
  ride: ['EMS → put the site in islanding-ready mode', 'Dispatch BESS-A + solar to hold voltage', 'Curtail DC-fast to protect the site', 'Ride the sag until the grid recovers'],
  island: ['Open the main grid breaker (disconnect from the grid)', 'EMS → Island mode on BESS-A + solar', 'Prioritise AC bays; shed DC-fast', 'Hold frequency and voltage stable'],
  priority: ['EMS → set load priority = AC bays first', 'Shed the DC-fast sessions', 'Stage a sequenced restart on supply return', 'Confirm the critical loads stay served'],
}

// Build a solid interactive procedure for ANY fault: bespoke where authored, else generated from
// the fault's own mitigation strategies so every fault still gets a rich, ordered, scored drill.
export function getProcedure(assetId, faultId) {
  const key = `${assetId}:${faultId}`
  if (P[key]) {
    const foc = STEP_FOCUS[key] || {}; const how = HOWTO[key] || {}
    return { key, objective: P[key].objective, steps: P[key].steps.map((st) => ({ ...st, focus: st.focus || foc[st.id], howto: st.howto || how[st.id] || STRAT_HOWTO[st.id] })) }
  }

  const strats = strategiesFor(assetId, faultId).filter((s) => s.key !== 'nothing')
  const steps = [
    { id: 'diag', title: 'Diagnose the fault', icon: '🔎', kind: 'diagnose', w: 0.05, seconds: 3,
      brief: 'Read the twin and confirm the failing subsystem.',
      detail: `Confirm the ${faultId.replace(/_/g, ' ')} on ${assetId} from live telemetry before you commit a response.`,
      mechanism: 'Every response is only as good as the diagnosis — identify the out-of-band signal on the digital twin first.',
      targets: ['ev:gridLoad', 'ev:transformerTemp', 'ev:faultedChargers'],
      diagnose: { prompt: 'Which reading is out of band?', options: [
        { signal: 'ev:gridLoad', label: 'Transformer load %', right: true },
        { signal: 'ev:solarOutput', label: 'Solar output kW' },
        { signal: 'ev:bessSoc', label: 'BESS state of charge' },
      ] },
      howto: GENERIC_HOWTO.diagnose,
      risk: 'Responding without a diagnosis risks fixing the wrong thing.' },
    ...strats.map((s, i) => ({
      id: s.key, title: s.name, icon: i === 0 ? '⭐' : '⚙️', kind: 'action', requires: ['diag'],
      w: Math.max(0.15, (s.readiness || 60) / 100 * 0.6), cost: 0.05 + i * 0.02, seconds: 6,
      brief: s.mech, detail: s.mech,
      mechanism: `Applies the "${s.name}" response; readiness ${s.readiness}% — the engine models this containing ~${s.readiness}% of the cascade.`,
      targets: ['ev:gridLoad', 'ev:faultedChargers', 'ev:bessPower'],
      generic: true,
      howto: STRAT_HOWTO[s.key] || [`Open the EMS / CPMS console for ${assetId}`, `Select the "${s.name}" response`, 'Apply it at the recommended level', 'Confirm the fault metric moves back into its healthy band'],
      risk: `Without "${s.name}", the fault keeps cascading across the site.`,
    })),
    { id: 'verify', title: 'Confirm stable & sign off', icon: '✅', kind: 'verify', requires: [strats[0]?.key || 'diag'], w: 0.05, seconds: 3, verifyWhen: 'stable',
      brief: 'Verify the site is back in band before closing.',
      detail: 'Close the incident only once the twin shows the site stabilised.',
      mechanism: 'The objective is met when the abnormal signals return to their healthy envelope.',
      targets: ['ev:gridLoad', 'ev:faultedChargers'],
      howto: GENERIC_HOWTO.verify,
      risk: 'A premature all-clear lets the fault re-develop.' },
  ]
  return { key, objective: `Contain the ${faultId.replace(/_/g, ' ')} on ${assetId} and stabilise the site.`, steps }
}

// Composite crisis/severity of a live frame → 0 (healthy) .. 1 (critical). Drives stability + $.
export function severityOf(fr) {
  const v = (k, lo, hi) => Math.max(0, Math.min(1, ((fr[k] ?? lo) - lo) / (hi - lo)))
  return Math.max(
    v('ev:gridLoad', 70, 106),
    v('ev:transformerTemp', 62, 98),
    v('ev:thermalRunawayRisk', 8, 70),
    v('ev:cellTempMax', 33, 50),
    (fr['ev:faultedChargers'] ?? 0) / 8,
    Math.max(0, Math.min(1, (30 - (fr['ev:loadHeadroom'] ?? 30)) / 30)),
  )
}

// signals that are meaningfully off-healthy in this frame → the ones that drift/heal in the drill
export function inPlaySignals(fr) {
  const out = []
  for (const k of Object.keys(HEALTHY)) {
    const d = Math.abs((fr[k] ?? HEALTHY[k]) - HEALTHY[k])
    const rel = d / (Math.abs(HEALTHY[k]) || 1)
    if (rel > 0.15 || (k === 'ev:faultedChargers' && (fr[k] || 0) > 0)) out.push(k)
  }
  return out
}

// letter grade from a 0..100 score
export function gradeLetter(score, safetyViol) {
  if (safetyViol) return { letter: 'F', label: 'FAILED — SAFETY', tone: 'crit' }
  if (score >= 90) return { letter: 'A', label: 'Outstanding', tone: 'ok' }
  if (score >= 80) return { letter: 'B', label: 'Strong', tone: 'ok' }
  if (score >= 70) return { letter: 'C', label: 'Passable', tone: 'warn' }
  if (score >= 55) return { letter: 'D', label: 'Weak', tone: 'warn' }
  return { letter: 'F', label: 'Failed', tone: 'crit' }
}
