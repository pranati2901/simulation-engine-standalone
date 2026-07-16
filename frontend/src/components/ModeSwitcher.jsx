import React from 'react'
import { useStore } from '../store.jsx'

export const MODES = [
  { id: 'decision', label: 'Decision', color: '#2563eb' },
  { id: 'training', label: 'Training', color: '#16a34a' },
  { id: 'twin', label: 'Twin', color: '#d97706' },
]

export default function ModeSwitcher() {
  const { mode, setMode } = useStore()
  return (
    <div className="mode-switch" role="tablist" aria-label="Mode">
      {MODES.map(m => (
        <button key={m.id} className={mode === m.id ? 'on' : ''} onClick={() => setMode(m.id)} role="tab" aria-selected={mode === m.id}>
          <span className="mdot" style={{ background: m.color }} />{m.label}
        </button>
      ))}
    </div>
  )
}
