import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The standalone SimCore frontend. It talks to the engine via a dev proxy so the browser
// sees one origin (no CORS to configure on the engine) — /engine/* is forwarded to the
// FastAPI engine on :8002. The X-API-Key header the browser sends is passed straight
// through. Nothing about the engine needs to change.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5200,
    strictPort: true,
    proxy: {
      '/engine': {
        target: process.env.ENGINE_URL || 'http://localhost:8002',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/engine/, ''),
      },
    },
  },
})
