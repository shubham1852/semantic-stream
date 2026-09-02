/**
 * components/layout/Topbar.jsx
 * Top navigation bar showing page title and live WebSocket status.
 */

import { useLocation, useNavigate } from 'react-router-dom'
import { Settings, Wifi, WifiOff } from 'lucide-react'
import Tooltip from '../ui/Tooltip'

const ROUTE_TITLES = {
  '/dashboard':   'Dashboard',
  '/upload':      'Upload & Analyse',
  '/experiments': 'Experiments',
  '/live':        'Live Camera',
  '/streaming':   'Streaming',
  '/analytics':   'Analytics',
  '/bandwidth':   'Bandwidth Simulator',
  '/history':     'History',
  '/reports':     'Reports',
  '/settings':    'Settings',
  '/research':    'Research',
}

// We use a simple prop for WS status rather than importing the hook here
// — the LivePage will be the one with a WS connection.
export default function Topbar({ wsConnected = false }) {
  const location = useLocation()
  const navigate = useNavigate()

  // Match dynamic segments like /results/:jobId and /streaming/:videoId
  const staticTitle = ROUTE_TITLES[location.pathname]
  const dynamicTitle =
    location.pathname.startsWith('/results/')   ? 'Analysis Results'  :
    location.pathname.startsWith('/streaming/') ? 'Streaming'         :
    null
  const title = staticTitle ?? dynamicTitle ?? 'SemanticStream'

  return (
    <header
      className="flex items-center justify-between px-6 py-3.5 shrink-0"
      style={{
        borderBottom: '1px solid rgba(79,70,229,0.1)',
        background: 'rgba(10,14,26,0.6)',
        backdropFilter: 'blur(12px)',
      }}
    >
      {/* Page title */}
      <div>
        <h1 className="font-display text-lg font-semibold text-text-primary">{title}</h1>
        <p className="text-xs text-text-muted mt-0.5">
          Semantic-Aware Adaptive Video Streaming
        </p>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-4">
        {/* WebSocket live indicator */}
        <Tooltip content={wsConnected ? 'WebSocket connected' : 'WebSocket disconnected'}>
          <div className="flex items-center gap-1.5">
            {wsConnected ? (
              <>
                <span className="live-dot" />
                <Wifi size={15} className="text-data-green" />
              </>
            ) : (
              <WifiOff size={15} className="text-text-muted" />
            )}
          </div>
        </Tooltip>

        {/* Settings button — navigates to /settings */}
        <button
          onClick={() => navigate('/settings')}
          className="text-text-muted hover:text-text-primary transition-colors p-1.5 rounded-btn hover:bg-white/5"
          title="Settings"
        >
          <Settings size={17} />
        </button>
      </div>
    </header>
  )
}

