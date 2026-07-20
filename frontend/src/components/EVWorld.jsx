import React, { useEffect, useRef } from 'react'
import { createEVWorld } from '../scene/evworld.js'

// EVWorld — mounts the Three.js "living energy site" (Gaadin charging hub) and streams a
// telemetry `live` frame onto it. `onAskAI(asset)` is wired to our grounded copilot.
export default function EVWorld({ live, onAskAI, height = 460 }) {
  const hostRef = useRef(null)
  const worldRef = useRef(null)
  const askRef = useRef(onAskAI)
  askRef.current = onAskAI

  useEffect(() => {
    if (!hostRef.current) return
    let world
    try { world = createEVWorld(hostRef.current, { onAskAI: (a) => askRef.current && askRef.current(a) }) }
    catch (e) { console.error('EV world failed to mount', e) }
    worldRef.current = world
    return () => { try { world && world.dispose() } catch {} ; worldRef.current = null }
  }, [])

  useEffect(() => {
    const w = worldRef.current
    if (w && w.update) { try { w.update(live || {}) } catch (e) { console.error('evworld update failed', e) } }
  }, [live])

  return <div ref={hostRef} className="hero3d scene3d-host evw-host"
    style={{ height, position: 'relative', padding: 0, overflow: 'hidden', borderRadius: 16 }} />
}
