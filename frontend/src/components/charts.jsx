import React from 'react'
// charts.jsx — small, dependency-free SVG chart primitives (donut, sparkline, histogram,
// tornado bars). Theme-aware via CSS vars. Kept generic so any mode can reuse them.

const polar = (cx, cy, r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)]
function arcPath(cx, cy, r, thick, a0, a1) {
  const large = a1 - a0 > Math.PI ? 1 : 0
  const [x0, y0] = polar(cx, cy, r, a0), [x1, y1] = polar(cx, cy, r, a1)
  const [xi1, yi1] = polar(cx, cy, r - thick, a1), [xi0, yi0] = polar(cx, cy, r - thick, a0)
  return `M${x0} ${y0} A${r} ${r} 0 ${large} 1 ${x1} ${y1} L${xi1} ${yi1} A${r - thick} ${r - thick} 0 ${large} 0 ${xi0} ${yi0} Z`
}

export function Donut({ data, size = 168, thickness = 24, center, sub }) {
  const total = data.reduce((a, d) => a + d.value, 0) || 1
  const r = size / 2, cx = r, cy = r
  let a = -Math.PI / 2
  return (
    <div style={{ display: 'flex', gap: 18, alignItems: 'center', flexWrap: 'wrap' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
        {data.map((d, i) => {
          const frac = d.value / total, a0 = a, a1 = a + frac * 2 * Math.PI; a = a1
          if (frac <= 0) return null
          return <path key={i} d={arcPath(cx, cy, r, thickness, a0, a1 - 0.012)} fill={d.color}><title>{d.label}: {Math.round(frac * 100)}%</title></path>
        })}
        {center != null && <text x={cx} y={cy - 2} textAnchor="middle" fontSize="21" fontWeight="800" fontFamily="var(--display)" fill="var(--text)">{center}</text>}
        {sub && <text x={cx} y={cy + 16} textAnchor="middle" fontSize="10.5" fill="var(--muted)">{sub}</text>}
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7, minWidth: 130 }}>
        {data.map((d, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: d.color, flexShrink: 0 }} />
            <span style={{ flex: 1, color: 'var(--muted)' }}>{d.label}</span>
            <b>{Math.round(100 * d.value / total)}%</b>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Sparkline({ values, w = 280, h = 60, color = 'var(--accent)', id = 'sp' }) {
  if (!values || values.length < 2) return <div className="hint">Not enough history yet — scan again to build the trend.</div>
  const mn = Math.min(...values), mx = Math.max(...values), span = mx - mn || 1
  const px = i => (i / (values.length - 1)) * (w - 6) + 3
  const py = v => h - 6 - ((v - mn) / span) * (h - 14)
  const pts = values.map((v, i) => `${px(i)},${py(v)}`).join(' ')
  const area = `M${px(0)},${h} L${values.map((v, i) => `${px(i)},${py(v)}`).join(' L')} L${px(values.length - 1)},${h} Z`
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ maxWidth: '100%', display: 'block' }}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity=".28" /><stop offset="100%" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      <path d={area} fill={`url(#${id})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={px(values.length - 1)} cy={py(values[values.length - 1])} r="3.5" fill={color} />
    </svg>
  )
}

export function Histogram({ bins, w = 340, h = 150, color = 'var(--accent)', markerIdx, labelFn }) {
  const max = Math.max(1, ...bins.map(b => b.count))
  const bw = (w - 8) / bins.length
  return (
    <svg width={w} height={h + 22} viewBox={`0 0 ${w} ${h + 22}`} style={{ maxWidth: '100%', display: 'block' }}>
      {bins.map((b, i) => {
        const bh = (b.count / max) * (h - 8)
        const hot = markerIdx === i
        return (
          <g key={i}>
            <rect x={i * bw + 4} y={h - bh} width={bw - 3} height={bh} rx="4"
              fill={hot ? 'var(--accent)' : color} opacity={hot ? 1 : 0.82}><title>{labelFn ? labelFn(b) : b.count}</title></rect>
          </g>
        )
      })}
      <line x1="0" y1={h} x2={w} y2={h} stroke="var(--border)" />
      {bins.length > 0 && <>
        <text x="4" y={h + 15} fontSize="9.5" fill="var(--muted)">{labelFn ? labelFn(bins[0], true) : ''}</text>
        <text x={w - 4} y={h + 15} fontSize="9.5" fill="var(--muted)" textAnchor="end">{labelFn ? labelFn(bins[bins.length - 1], true) : ''}</text>
      </>}
    </svg>
  )
}

// diverging horizontal bars around a baseline — a tornado chart
export function Tornado({ rows, w = 360, fmt = v => v }) {
  const max = Math.max(1, ...rows.map(r => r.swing))
  const rowH = 34, padL = 108, barW = w - padL - 8
  return (
    <svg width={w} height={rows.length * rowH + 8} viewBox={`0 0 ${w} ${rows.length * rowH + 8}`} style={{ maxWidth: '100%', display: 'block' }}>
      {rows.map((r, i) => {
        const y = i * rowH + 6, bw = (r.swing / max) * barW
        return (
          <g key={i}>
            <text x={padL - 8} y={y + rowH / 2 - 3} textAnchor="end" fontSize="11.5" fontWeight="600" fill="var(--text)">{r.label}</text>
            <rect x={padL} y={y + 3} width={Math.max(2, bw)} height={rowH - 16} rx="5" fill="var(--accent)" opacity={0.55 + 0.45 * (r.swing / max)}><title>{fmt(r.swing)}</title></rect>
            <text x={padL + Math.max(2, bw) + 6} y={y + rowH / 2 - 3} fontSize="11" fontWeight="700" fill="var(--muted)">{fmt(r.swing)}</text>
          </g>
        )
      })}
    </svg>
  )
}
