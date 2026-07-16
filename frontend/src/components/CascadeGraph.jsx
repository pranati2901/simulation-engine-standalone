import React from 'react'
import { layoutGraph, nodeExposure, money, NODE_W, NODE_H } from '../impact.js'

const TINT = { low: '#eef2f7', medium: '#fef6e7', high: '#fdeede', critical: '#fdeaea' }

function edgePath(a, b) {
  const x1 = a.x + NODE_W, y1 = a.y + NODE_H / 2, x2 = b.x, y2 = b.y + NODE_H / 2, mx = (x1 + x2) / 2
  return `M${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`
}
function twoLines(s, max = 22) {
  const words = String(s || '').split(' '); const out = ['']
  for (const w of words) {
    if (out[out.length - 1] && (out[out.length - 1] + ' ' + w).length > max) { if (out.length < 2) out.push(w); else { out[1] += '…'; break } }
    else out[out.length - 1] = (out[out.length - 1] ? out[out.length - 1] + ' ' + w : w)
  }
  return out
}
// Same nodes, different intelligence per mode — this is what makes it three engines, not a reskin.
function metric(n, mode, domain) {
  if (mode === 'training') return n.kind === 'fault' ? '⚑ scored decision' : 'consequence'
  if (mode === 'twin') return `${(n.impact || '').toUpperCase()} · risk`
  return money(nodeExposure(domain, n.impact))   // decision / reports → $ per node
}

export default function CascadeGraph({ graph, selectedId, onSelect, mode = 'decision' }) {
  const { nodes, edges, w, h } = layoutGraph(graph)
  if (!nodes.length) return null
  const domain = graph?.domain
  return (
    <div style={{ overflowX: 'auto' }}>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ maxWidth: '100%', display: 'block' }}>
        {edges.map((e, i) => (
          <path key={i} d={edgePath(e.a, e.b)} fill="none"
            stroke={e.preventable ? 'var(--red)' : '#c3ccd8'} strokeWidth={e.preventable ? 2 : 1.5}
            strokeDasharray={e.preventable ? '5 4' : ''} />
        ))}
        {nodes.map(n => {
          const fault = n.kind === 'fault'
          const sel = selectedId === n.id
          const lines = twoLines(n.label)
          return (
            <g key={n.id} transform={`translate(${n.x},${n.y})`} onClick={() => onSelect && onSelect(n.id)} style={{ cursor: onSelect ? 'pointer' : 'default' }}>
              <rect width={NODE_W} height={NODE_H} rx="9"
                fill={fault ? 'var(--accent)' : (TINT[n.impact] || '#eef2f7')}
                stroke={sel ? '#111827' : (fault ? 'var(--accent)' : '#dbe2ec')} strokeWidth={sel ? 2.5 : 1} />
              {lines.map((ln, i) => (
                <text key={i} x="11" y={13 + i * 13} fontSize="10.5" fontWeight="600" fill={fault ? '#fff' : '#16202e'}>{ln}</text>
              ))}
              <text x="11" y={NODE_H - 8} fontSize="9.5" fontWeight="700" fill={fault ? 'rgba(255,255,255,.85)' : 'var(--muted)'}>{metric(n, mode, domain)}</text>
            </g>
          )
        })}
      </svg>
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: 'var(--muted)', flexWrap: 'wrap' }}>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, background: 'var(--accent)', borderRadius: 3, verticalAlign: -1, marginRight: 5 }} />root fault</span>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#fdeede', border: '1px solid #dbe2ec', borderRadius: 3, verticalAlign: -1, marginRight: 5 }} />consequence</span>
        <span><span style={{ display: 'inline-block', width: 14, height: 0, borderTop: '2px dashed var(--red)', verticalAlign: 3, marginRight: 5 }} />preventable</span>
        <span style={{ marginLeft: 'auto', fontStyle: 'italic' }}>{mode === 'twin' ? 'per-node: failure severity' : mode === 'training' ? 'per-node: decision vs consequence' : 'per-node: $ exposure'}{onSelect ? ' · click to inspect' : ''}</span>
      </div>
    </div>
  )
}
