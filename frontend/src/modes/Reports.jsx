import React, { useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { compareInvestments, execSummary } from '../analysis.js'
import { exposureByCategory, exposureAt, money } from '../impact.js'
import { getAssumptions, saveAssumptions, resetAssumptions } from '../assumptions.js'
import CascadeGraph from '../components/CascadeGraph.jsx'
import { Logo } from '../brand.jsx'

// Reports — the board-ready output, and the assumptions it is computed from, on one page.
//
// These were two pages and shouldn't have been: every $ figure in a report comes out of
// the assumptions, so reading a number and asking "where does that come from?" used to
// mean leaving the page. Same category, one page, one toggle.

function Row({ label, value, onChange }) {
  return (
    <div className="field-row">
      <span>{label}</span>
      <span style={{ color: 'var(--muted)' }}>$</span>
      <input className="lib-search" style={{ width: 120, padding: '7px 10px' }} type="number" min="0"
        value={value} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

const COSTS = [['cross', 'Cross-train existing staff'], ['std', 'Hire + standard training'], ['full', 'Full readiness program']]

function AssumptionsView({ onChanged }) {
  const { domains } = useStore()
  const [a, setA] = useState(getAssumptions())
  const [saved, setSaved] = useState(false)
  const upM = (k, v) => setA(x => ({ ...x, money: { ...x.money, [k]: Math.max(0, +v || 0) } }))
  const upC = (k, v) => setA(x => ({ ...x, cost: { ...x.cost, [k]: Math.max(0, +v || 0) } }))
  const save = () => {
    saveAssumptions(a); setSaved(true); setTimeout(() => setSaved(false), 1600)
    // Every $ on the report recomputes from these. A stale report next to edited
    // assumptions is worse than no report — drop it and make them regenerate.
    onChanged?.()
  }
  const reset = () => { resetAssumptions(); setA(getAssumptions()); onChanged?.() }

  return (
    <div className="grid">
      <div className="col">
        <div className="card">
          <div className="card-title">Impact rate<span className="tag">$ per severity unit</span></div>
          <div className="hint" style={{ marginBottom: 12 }}>What one unit of weighted impact costs, per vertical.</div>
          {domains.map(d => <Row key={d.key} label={d.name} value={a.money[d.key] ?? a.money.default} onChange={v => upM(d.key, v)} />)}
          <Row label="Default (other)" value={a.money.default} onChange={v => upM('default', v)} />
        </div>
      </div>
      <div className="col">
        <div className="card">
          <div className="card-title">Intervention cost<span className="tag">$ per strategy</span></div>
          <div className="hint" style={{ marginBottom: 12 }}>What each readiness investment costs.</div>
          {COSTS.map(([k, label]) => <Row key={k} label={label} value={a.cost[k]} onChange={v => upC(k, v)} />)}
        </div>
        <div className="card">
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary" style={{ flex: 1 }} onClick={save}>{saved ? '✓ Saved' : 'Save assumptions'}</button>
            <button className="btn" onClick={reset}>Reset to defaults</button>
          </div>
          <div className="hint" style={{ marginTop: 10 }}>
            Saved in your browser. Every $ figure across the platform recomputes from these —
            nothing financial is hard-coded. The engine models physics and operations; the money
            model is yours.
          </div>
        </div>
      </div>
    </div>
  )
}

function ReportView({ rep, setRep }) {
  const { allScenarios } = useStore()
  const [sid, setSid] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const scenario = allScenarios.find(s => s.id === sid) || null

  const generate = async () => {
    if (!scenario) return
    setBusy(true); setErr(null); setRep(null)
    try {
      const cmp = await compareInvestments(scenario, scenario.domainKey)
      const mc = await api.monteCarlo(scenario.id, scenario.domainKey).catch(() => null)
      const p05 = mc?.kpi_stats?.containment_rate?.p05 ?? 0
      const var95 = exposureAt(cmp.full, cmp.prevPot, p05)
      const causes = exposureByCategory(cmp.worst.graph)
      const cert = cmp.rows[cmp.rows.length - 1].graph?.nodes?.[0]?.result   // full-readiness run
      setRep({ scenario, cmp, mc, var95, causes, cert, summary: execSummary({ scenario, domainName: scenario.domainName, cmp }) })
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const maxCause = rep ? Math.max(1, ...rep.causes.map(c => c.value)) : 1

  return (
    <>
      <div className="card no-print" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <select className="select" style={{ flex: 1 }} value={sid} onChange={e => setSid(e.target.value)}>
          <option value="">Choose a scenario…</option>
          {allScenarios.map(s => <option key={s.id} value={s.id}>{s.domainName?.split(' ')[0]} · {s.name}</option>)}
        </select>
        <button className="btn btn-primary" onClick={generate} disabled={busy || !scenario}>{busy ? <><span className="spin" /> Generating…</> : 'Generate report'}</button>
        {rep && <button className="btn" onClick={() => window.print()}>⤓ Export PDF</button>}
      </div>
      {err && <div className="err" style={{ marginTop: 12 }}>{err}</div>}

      {rep && (
        <div className="report">
          <div className="rep-head">
            <div>
              <div className="rep-title">{rep.scenario.name}</div>
              <div className="rep-sub">{rep.scenario.domainName} · Operational Intelligence Report · {new Date().toLocaleDateString()}</div>
            </div>
            <div className="rep-logo"><Logo size={22} /> Goalcert</div>
          </div>

          <div className="stat-row" style={{ marginBottom: 18 }}>
            <div className="hero-stat"><div className="v">{money(rep.cmp.full)}</div><div className="l">exposure (unmitigated)</div></div>
            <div className="hero-stat"><div className="v" style={{ color: 'var(--red)' }}>{money(rep.cmp.prevPot)}</div><div className="l">avoidable</div></div>
            <div className="hero-stat"><div className="v">{money(rep.var95)}</div><div className="l">95% value-at-risk</div></div>
            <div className="hero-stat"><div className="v" style={{ color: 'var(--green)' }}>{rep.cmp.best ? `${rep.cmp.best.roi.toFixed(1)}×` : '—'}</div><div className="l">best ROI</div></div>
          </div>

          <div className="rep-sec"><h3>Executive summary</h3><p>{rep.summary}</p></div>

          <div className="rep-sec"><h3>Where the exposure comes from</h3>
            {rep.causes.map((c, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5 }}><b style={{ textTransform: 'capitalize' }}>{c.category}</b><span>{money(c.value)} · {c.pct}%</span></div>
                <div className="bar-track" style={{ marginTop: 3, height: 7 }}><div className="bar-fill" style={{ width: `${100 * c.value / maxCause}%`, background: 'var(--accent)' }} /></div>
              </div>
            ))}
          </div>

          <div className="rep-sec"><h3>Investment options</h3>
            <table className="cmp">
              <thead><tr><th>Investment</th><th>Exposure</th><th>Avoided</th><th>Cost</th><th>ROI</th></tr></thead>
              <tbody>{rep.cmp.rows.map(r => (
                <tr key={r.key} className={rep.cmp.best && rep.cmp.best.key === r.key ? 'rec' : ''}>
                  <td><b>{r.name}</b></td><td>{money(r.exposure)}</td>
                  <td style={{ color: r.saved >= 1 ? 'var(--green)' : 'var(--muted)' }}>{r.saved >= 1 ? '+' + money(r.saved) : '—'}</td>
                  <td>{r.cost ? money(r.cost) : '—'}</td><td>{r.roi ? `${r.roi.toFixed(1)}×` : '—'}</td>
                </tr>))}</tbody>
            </table>
            <div className="hint" style={{ marginTop: 8 }}>Costs and $ rates come from Assumptions — toggle above to change them.</div>
          </div>

          {rep.cert && (
            <div className="rep-sec"><h3>Compliance evidence</h3>
              <div className="cert">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Fully-resourced response, deterministic run</span>
                  <span className={`pill ${rep.cert.summary?.clearance?.certified ? 'pill-green' : 'pill-red'}`}>{rep.cert.summary?.clearance?.certified ? 'CERTIFIED' : 'NOT CERTIFIED'}</span>
                </div>
                <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {(rep.cert.objectives?.operator || []).map((o, i) => (
                    <div key={i} style={{ fontSize: 12.5 }}><span style={{ color: o.met ? 'var(--green)' : 'var(--red)', fontWeight: 800, marginRight: 8 }}>{o.met ? '✓' : '✗'}</span>{o.text}</div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="rep-sec"><h3>Cascade</h3><CascadeGraph graph={rep.cmp.worst.graph} /></div>
        </div>
      )}
    </>
  )
}

export default function Reports() {
  const [view, setView] = useState('report')
  // Lifted so switching to Assumptions and back doesn't throw away a generated report —
  // it's several engine runs plus a Monte Carlo, and regenerating it is slow.
  const [rep, setRep] = useState(null)

  return (
    <>
      <div className="mode-head no-print" style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <h2>{view === 'report' ? 'Reports' : 'Model Assumptions'}</h2>
          <p>{view === 'report'
            ? 'Board-ready executive summary, explainability and compliance evidence — one click.'
            : 'The financial inputs a physics/ops simulation can’t provide — your model, editable.'}</p>
        </div>
        <div className="seg">
          <button className={view === 'report' ? 'on' : ''} onClick={() => setView('report')}>Report</button>
          <button className={view === 'assumptions' ? 'on' : ''} onClick={() => setView('assumptions')}>Assumptions</button>
        </div>
      </div>

      {view === 'report'
        ? <ReportView rep={rep} setRep={setRep} />
        : <AssumptionsView onChanged={() => setRep(null)} />}
    </>
  )
}
