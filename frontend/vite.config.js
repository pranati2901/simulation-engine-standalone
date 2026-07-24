import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The SimCore frontend. The browser sees one origin; the dev proxy forwards to two engines:
//   /engine/*  → SimCore FastAPI engine (:8002), X-API-Key passed straight through
//   /api/*, /ws/* → the embedded Cybersecurity (GoalCert) FastAPI engine (:8000)
// In Docker/prod the same routing is done by the nginx gateway instead of this proxy.
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
      // Cybersecurity (GoalCert) engine — its API and WebSockets keep their native paths.
      '/api': {
        target: process.env.CYBER_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.CYBER_URL || 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
