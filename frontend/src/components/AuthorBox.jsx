import React, { useState } from 'react'
import { useStore } from '../store.jsx'
import { api } from '../api.js'

export default function AuthorBox() {
  const { domain, reloadScenarios, setScenarioId } = useStore()
  const [prompt, setPrompt] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [done, setDone] = useState(null)

  const go = async () => {
    if (!prompt.trim()) return
    setBusy(true); setErr(null); setDone(null)
    try {
      const s = await api.author(domain, prompt.trim())
      await reloadScenarios(); setScenarioId(s.id); setDone(s); setPrompt('')
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  // SOP → scenario: read a procedure file and feed it to the same authoring endpoint.
  const importSop = (e) => {
    const f = e.target.files?.[0]; if (!f) return
    const r = new FileReader()
    r.onload = () => setPrompt(`Turn this operating procedure into a fault scenario and drill:\n\n${String(r.result).slice(0, 4000)}`)
    r.readAsText(f); e.target.value = ''
  }

  return (
    <div className="card">
      <div className="card-title">Author a drill<span className="tag">AI</span></div>
      <div className="hint" style={{ marginBottom: 8 }}>Describe a failure in plain English — or import an SOP — and the engine writes a runnable, scored scenario.</div>
      <textarea className="input" rows={3} value={prompt} disabled={busy}
        placeholder="e.g. a points machine jams at peak hour and the controller must reroute trains…"
        onChange={e => setPrompt(e.target.value)} />
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <label className="btn" style={{ flexShrink: 0 }}>📄 Import SOP<input type="file" accept=".txt,.md,.csv,.text,.log" style={{ display: 'none' }} onChange={importSop} /></label>
        <button className="btn btn-primary" style={{ flex: 1 }} onClick={go} disabled={busy || !prompt.trim()}>
          {busy ? <><span className="spin" /> Authoring…</> : 'Author drill'}
        </button>
      </div>
      {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}
      {done && <div style={{ marginTop: 10, fontSize: 12.5 }}><span className="pill pill-green">added</span> <b>{done.name}</b> — selected below, ready to run.</div>}
    </div>
  )
}
