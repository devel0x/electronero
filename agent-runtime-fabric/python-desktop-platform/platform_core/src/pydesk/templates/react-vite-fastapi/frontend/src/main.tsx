import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'

function App() {
  const [backendMessage, setBackendMessage] = useState('Not called yet')
  const [bridgeMessage, setBridgeMessage] = useState('Not called yet')

  async function callBackend() {
    const response = await fetch('http://127.0.0.1:8000/api/ping')
    const data = await response.json()
    setBackendMessage(data.message)
  }

  async function callBridge() {
    // @ts-ignore pywebview injects this at runtime
    const info = await window.pywebview.api.app_paths()
    setBridgeMessage(JSON.stringify(info))
  }

  return (
    <main style={{ fontFamily: 'Inter, Arial, sans-serif', margin: 24 }}>
      <h1>PyDesk React + Vite + FastAPI Template</h1>
      <p>Backend: {backendMessage}</p>
      <p>Bridge: {bridgeMessage}</p>
      <button onClick={callBackend}>Call FastAPI</button>
      <button onClick={callBridge} style={{ marginLeft: 8 }}>Call Native Bridge</button>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
