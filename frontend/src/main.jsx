import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { StoreProvider } from './store.jsx'
import './styles.css'

// The .sc-root wrapper is not cosmetic: vite.config.js rewrites every selector in
// styles.css to live under it, so the app renders unstyled without it. ScenarioRemoteApp
// renders the same wrapper when the hub mounts us — one stylesheet, both shells.
createRoot(document.getElementById('root')).render(
  <div className="sc-root">
    <BrowserRouter>
      <StoreProvider>
        <App />
      </StoreProvider>
    </BrowserRouter>
  </div>,
)
