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
// Pins that are NOT free to change (integration plan §0.1): React 18.3 (federation shares
// ONE React instance across host and remotes — a 19-built remote crashes the moment it
// touches a 19-only API; AUTOMIND had to be downgraded for exactly this) and Vite 5.4
// (@originjs/vite-plugin-federation is not verified on Vite 6+).
export default defineConfig({
  // Absolute origin in the hub build, so assets resolve against the ENGINE's origin rather
  // than the hub's. Without it the hub requests our assets from its own host and 404s —
  // the twin's turbine.glb did exactly this.
  base: process.env.VITE_REMOTE_BASE || '/',
  plugins: [
    react(),
    federation({
      name: 'scenarioEngine',
      filename: 'remoteEntry.js',
      // ONE exposed component. Not the providers, not the router — those are composed
      // INSIDE ScenarioRemoteApp with our own module instances (plan §0.2).
      exposes: {
        './ScenarioRemoteApp': './src/ScenarioRemoteApp.jsx',
      },
      // React must be ONE instance across host+remote or hooks break — that is the only
      // true singleton requirement. react-router lives only inside this remote's own tree
      // (ScenarioRemoteApp mounts its own MemoryRouter), so it keeps its own copy. Same
      // shape as the twin and agentic remotes; the hub host shares exactly these two.
      shared: ['react', 'react-dom'],
    }),
  ],
  build: {
    target: 'esnext',      // required by module federation
    cssCodeSplit: false,   // one stylesheet the host can link deterministically
    rollupOptions: {
      output: {
        // The hub derives the CSS href by string-replacing remoteEntry.js -> style.css,
        // so this filename must stay stable and unhashed (plan §0.11).
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
