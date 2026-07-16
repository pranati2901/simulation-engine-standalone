import React, { useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'
import { compareInvestments, execSummary } from '../analysis.js'
import { exposureByCategory, exposureAt, money } from '../impact.js'
import CascadeGraph from '../components/CascadeGraph.jsx'

export default function Reports() {
  const { allScenarios } = useStore()
  const [sid, setSid] = useState('')
  const [rep, setRep] = useState(null)
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
      setRep({ cmp, mc, var95, causes, cert, summary: execSummary({ scenario, domainName: scenario.domainName, cmp }) })
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const maxCause = rep ? Math.max(1, ...rep.causes.map(c => c.value)) : 1

  return (
    <>
      <div className="mode-head no-print"><h2>Reports</h2><p>Board-ready executive summary, explainability and compliance evidence — one click.</p></div>

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
              <div className="rep-title">{scenario.name}</div>
              <div className="rep-sub">{scenario.domainName} · Operational Intelligence Report · {new Date().toLocaleDateString()}</div>
            </div>
            <div className="rep-logo">◆ SimCore</div>
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
