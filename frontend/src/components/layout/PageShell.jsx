/**
 * components/layout/PageShell.jsx
 * Root layout: Sidebar + Topbar + main content area + Toast container.
 */

import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { ToastContainer } from '../ui/Toast'

export default function PageShell({ wsConnected = false }) {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--color-bg-primary)' }}>
      {/* Sidebar */}
      <Sidebar />

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Topbar wsConnected={wsConnected} />

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
