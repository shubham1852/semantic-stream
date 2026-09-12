/**
 * components/layout/PageShell.jsx
 * Root layout: Sidebar + Topbar + main content area + Toast container.
 */

import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { ToastContainer } from '../ui/Toast'

const PING_INTERVAL_MS = 10_000

export default function PageShell({ wsConnected = false }) {
  const [backendOnline, setBackendOnline] = useState(false)

  /* Lightweight backend heartbeat — ping /health every 10 s */
  useEffect(() => {
    let cancelled = false
    const ping = async () => {
      try {
        const res = await fetch('/health', { method: 'GET', cache: 'no-store' })
        if (!cancelled) setBackendOnline(res.ok)
      } catch {
        if (!cancelled) setBackendOnline(false)
      }
    }
    ping()                                           // immediate first check
    const id = setInterval(ping, PING_INTERVAL_MS)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  // wsConnected = true only when LivePage has an active WebSocket.
  // backendOnline = true whenever the FastAPI /health endpoint responds.
  const connected = wsConnected || backendOnline

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--color-bg-primary)' }}>
      {/* Sidebar */}
      <Sidebar />

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Topbar wsConnected={connected} />

        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-screen-xl mx-auto animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Global toast notifications */}
      <ToastContainer />
    </div>
  )
}
