// brand.jsx — the Goalcert mark, identical to the hub's (hub/web/src/lib.jsx).
//
// Inlined as SVG rather than imported as a file: an absolute asset path (/logo.png)
// resolves against the HUB's origin once federated and 404s — the exact failure the
// twin's turbine.glb hit. An inline SVG has no origin to get wrong.
//
// The gradient id is namespaced (sc-brand-grad). The hub renders its own copy of this
// mark with id "gcg"; two elements with the same id in one document is a real collision
// and the second gradient silently loses.
import React from 'react'

export function Logo({ size = 32 }) {
  return (
    <span className="sc-brand-mark" style={{ width: size, height: size }} aria-hidden="true"
      dangerouslySetInnerHTML={{ __html:
        `<svg viewBox="0 0 120 120" width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
          <defs><linearGradient id="sc-brand-grad" x1="14" y1="14" x2="106" y2="106" gradientUnits="userSpaceOnUse">
            <stop stop-color="#7c3aed"/><stop offset="1" stop-color="#2563eb"/></linearGradient></defs>
          <circle cx="60" cy="62" r="33" stroke="url(#sc-brand-grad)" stroke-width="13" fill="none"/>
          <rect x="53" y="11" width="14" height="100" rx="3" fill="url(#sc-brand-grad)"/>
          <rect x="44" y="11" width="32" height="9" rx="3" fill="url(#sc-brand-grad)"/>
          <rect x="44" y="102" width="32" height="9" rx="3" fill="url(#sc-brand-grad)"/>
        </svg>` }} />
  )
}

export function Brand({ size = 30 }) {
  return (
    <div className="sc-brand">
      <Logo size={size} />
      <div className="sc-brand-word">
        <div className="sc-brand-name">Goalcert</div>
        <div className="sc-brand-tag">Scenario Engine</div>
      </div>
    </div>
  )
}
