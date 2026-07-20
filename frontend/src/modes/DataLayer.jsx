import React, { useState } from 'react'
import { MODEL, loadNetwork, resetNetwork, isDefaultNetwork } from '../ev/networkModel.js'

// The connector architecture (mirrors the data-requirements sheet). "sample" = provided by the
// bundled demo network; "off" = would connect to the customer's live system at deployment.
const CONNECTORS = [
  { key: 'ocpp', name: 'OCPP 1.6 / 2.0.1', pull: 'Charger status, MeterValues, sessions, fault codes', status: 'sample' },
  { key: 'scada', name: 'SCADA / EMS', pull: 'Feeder load, transformer & BESS temperature, voltage', status: 'sample' },
  { key: 'meters', name: 'Smart meters', pull: 'Real-time kW / kWh at each point', status: 'sample' },
  { key: 'tariff', name: 'Utility tariff & SLA', pull: 'ToU price, demand charges, uptime penalties', status: 'sample' },
  { key: 'weather', name: 'Weather API', pull: 'Temperature, irradiance, rain forecast', status: 'off' },
  { key: 'erp', name: 'ERP / CMMS', pull: 'O&M cost, spares, fault & repair history', status: 'off' },
]

const badge = (s) => s === 'sample'
  ? <span className="pill pill-green">● sample data</span>
  : <span className="pill pill-muted">not connected</span>

export default function DataLayer() {
  const [, force] = useState(0)
  const [json, setJson] = useState('')
  const [msg, setMsg] = useState(null)

  const apply = () => {
    try {
      const net = JSON.parse(json)
      if (!net || !Array.isArray(net.assets) || !net.assets.length) throw new Error('need an "assets" array')
      loadNetwork(net); setMsg({ ok: true, text: `Loaded "${MODEL.site}" — ${MODEL.assets.length} assets. The simulator now runs on this network.` }); force(x => x + 1)
    } catch (e) { setMsg({ ok: false, text: `Couldn't parse: ${e.message}` }) }
  }
  const reset = () => { resetNetwork(); setMsg({ ok: true, text: 'Reset to the Gaadin sample network.' }); setJson(''); force(x => x + 1) }
  const loadSample = () => setJson(JSON.stringify({ site: MODEL.site, currency: MODEL.currency, cost: MODEL.cost, assets: MODEL.assets }, null, 2))

  return (
    <>
      <div className="mode-head">
        <h2>Company Data Layer</h2>
        <p>SimCore never invents results. It builds a live model of your real operation from the systems below — then the engine computes outcomes on <b>your</b> data.</p>
      </div>

      <div className="card">
        <div className="card-title">Data connectors</div>
        <div className="conn-grid">
          {CONNECTORS.map(c => (
            <div key={c.key} className="conn-card">
              <div className="conn-h"><b>{c.name}</b>{badge(c.status)}</div>
              <div className="conn-p">{c.pull}</div>
              <button className="btn btn-block" style={{ marginTop: 10 }} disabled={c.status === 'sample'}>
                {c.status === 'sample' ? 'Active (demo)' : 'Connect →'}
              </button>
            </div>
          ))}
        </div>
        <div className="hint" style={{ marginTop: 10 }}>Live connections need the customer's credentials — enabled at deployment. The demo runs on a bundled sample network so every number is still real math, just on representative data.</div>
      </div>

      <div className="grid" style={{ marginTop: 16 }}>
        <div className="col">
          <div className="card">
            <div className="card-title">Active network<span className="tag">{isDefaultNetwork() ? 'sample' : 'imported'}</span></div>
            <div className="stat-row" style={{ marginBottom: 12 }}>
              <div className="hero-stat"><div className="v" style={{ fontSize: 18 }}>{MODEL.site}</div><div className="l">site</div></div>
              <div className="hero-stat"><div className="v">{MODEL.assets.length}</div><div className="l">assets</div></div>
              <div className="hero-stat"><div className="v">{MODEL.currency} {MODEL.cost.rev_inr_per_kwh}/kWh</div><div className="l">tariff</div></div>
            </div>
            {MODEL.assets.map(a => (
              <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                <b>{a.name}</b><span style={{ color: 'var(--muted)' }}>{a.type} · {(a.faults || []).length} fault modes</span>
              </div>
            ))}
          </div>
        </div>
        <div className="col">
          <div className="card">
            <div className="card-title">Import a network</div>
            <div className="hint" style={{ marginBottom: 8 }}>Paste a network export (JSON) — matches the data-requirements schema. The ask-box, scenarios and copilot all switch to it.</div>
            <textarea className="ne-input" style={{ width: '100%', height: 200, fontFamily: 'monospace', fontSize: 11.5 }} value={json}
              onChange={e => setJson(e.target.value)} placeholder='{ "site": "...", "cost": {...}, "assets": [ {"id":"TX-1","name":"...","type":"transformer","faults":["overload"]} ] }' />
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn btn-primary" onClick={apply} disabled={!json.trim()}>Apply network</button>
              <button className="btn" onClick={loadSample}>Load sample JSON</button>
              <button className="btn btn-ghost" style={{ marginLeft: 'auto' }} onClick={reset}>↺ Reset to sample</button>
            </div>
            {msg && <div className="hint" style={{ marginTop: 10, color: msg.ok ? 'var(--green)' : 'var(--red)' }}>{msg.text}</div>}
          </div>
        </div>
      </div>
    </>
  )
}
