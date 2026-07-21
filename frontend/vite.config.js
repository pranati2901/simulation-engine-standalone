import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import federation from '@originjs/vite-plugin-federation'

// The Goalcert Scenario Engine frontend. Two lives from one codebase:
//
// STANDALONE (npm run dev): talks to the engine via a dev proxy so the browser sees one
// origin — /engine/* forwards to the FastAPI engine on :8002. Nothing about the engine
// needs to change and there is no CORS to configure.
//
// FEDERATED (npm run build): exposes ONE self-contained component, ScenarioRemoteApp, that
// the Integration Hub mounts. The hub sets window.__SC_API_BASE__ = '/api/scenario' before
// mounting, so every call routes through the hub's gateway instead of this proxy.
//
// Pins that are NOT free to change: React 18.3 (federation shares ONE React instance across
// host and remotes — a 19-built remote crashes the moment it touches a 19-only API) and
// Vite 5.4 (@originjs/vite-plugin-federation is not verified on Vite 6+).

// ── CSS scoping ─────────────────────────────────────────────────────────────────
//
// Module Federation does not isolate CSS. The hub links our style.css into ITS <head>, so
// every bare rule in styles.css — `body`, `*`, `.card`, `.page`, `.panel` — would restyle
// the hub's own chrome. 769 lines is too many to hand-scope and too easy to regress, so we
// rewrite selectors at build time instead: everything ends up under `.sc-root`, the wrapper
// that ScenarioRemoteApp (and main.jsx, standalone) renders.
//
// `body` / `html` / `:root` BECOME `.sc-root` rather than sitting under it — they are the
// document-level rules whose job the wrapper now does, including the custom properties.
// Selectors that could apply to the wrapper itself (`.foo`, `[data-mode=…]`) get both the
// descendant and the self form, because ScenarioRemoteApp puts data-mode on .sc-root.
const SCOPE = '.sc-root'

function scopeSelector(sel) {
  const s = sel.trim()
  if (!s || s.startsWith(SCOPE)) return s          // already scoped — leave it alone
  const root = s.match(/^(:root|html|body)\b/)
  if (root) return (SCOPE + s.slice(root[0].length)).trim()
  if (s === '*') return `${SCOPE}, ${SCOPE} *`
  if (/^[.[:#]/.test(s)) return `${SCOPE} ${s}, ${SCOPE}${s}`
  return `${SCOPE} ${s}`
}

function scopeCss() {
  return {
    postcssPlugin: 'goalcert-scope-css',
    Rule(rule) {
      // Keyframe steps (`from`, `50%`) are not selectors — prefixing them silently kills
      // every animation in the app.
      if (rule.parent?.type === 'atrule' && /keyframes/.test(rule.parent.name)) return
      if (rule.__scoped) return
      rule.__scoped = true
      rule.selectors = rule.selectors.map(scopeSelector)
    },
  }
}
scopeCss.postcss = true

export default defineConfig({
  // Left as '/' ON PURPOSE, even though we are loaded cross-origin by the hub.
  //
  // Every URL in this bundle is a module specifier, and those resolve against the URL of
  // the module doing the importing — remoteEntry.js, served from the ENGINE. So '/assets/x'
  // inside it already means the engine's /assets/x, not the hub's. (That is only true
  // because we ship no public/ directory and no import.meta.env.BASE_URL string-building;
  // the twin's turbine.glb needed an absolute base precisely because it was neither.)
  //
  // Setting an absolute base actively BREAKS the remote's own stylesheet: the federation
  // plugin builds that href as base + filename and drops the assets/ directory, so the
  // engine gets a request for /style.css and ORB blocks the 404. Override only if this
  // bundle ever grows a public/ asset — and fix that href if you do.
  base: process.env.VITE_REMOTE_BASE || '/',
  plugins: [
    react(),
    federation({
      name: 'scenarioEngine',
      filename: 'remoteEntry.js',
      // ONE exposed component. Not the providers, not the router — those are composed
      // INSIDE ScenarioRemoteApp with our own module instances.
      exposes: {
        './ScenarioRemoteApp': './src/ScenarioRemoteApp.jsx',
      },
      // React must be ONE instance across host+remote or hooks break — that is the only
      // true singleton requirement. react-router and three live only inside this remote's
      // own tree, so they keep their own copies. The hub host shares exactly these two.
      //
      // NOTE this stays safe only because our 3-D is raw three.js (src/scene/evworld.js),
      // not @react-three/fiber. R3F bundles its own react-reconciler, which binds to a
      // different React copy than the shared one and throws React #321 — that is what broke
      // the twin panel, and its fix was to stop sharing React and self-mount instead. If a
      // page here ever adopts R3F, apply that same mount() pattern.
      shared: ['react', 'react-dom'],
    }),
  ],
  css: {
    postcss: { plugins: [scopeCss()] },
  },
  build: {
    target: 'esnext',      // required by module federation
    cssCodeSplit: false,   // one stylesheet the host can link deterministically
    rollupOptions: {
      output: {
        // The hub derives the CSS href by string-replacing remoteEntry.js -> style.css,
        // so this filename must stay stable and unhashed.
        assetFileNames: (info) =>
          info.name?.endsWith('.css') ? 'assets/style.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
  server: {
    port: 5200,
    strictPort: true,
    proxy: {
      '/engine': {
        target: process.env.ENGINE_URL || 'http://127.0.0.1:8002',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/engine/, ''),
      },
    },
  },
  preview: { port: 5200, strictPort: true },
})
