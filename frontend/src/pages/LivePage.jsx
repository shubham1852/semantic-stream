/**
 * pages/LivePage.jsx
 * Full live camera analysis with real-time detection panel.
 */

import { useState } from 'react'
import { Camera, Eye, Activity, Shield } from 'lucide-react'
import LiveCameraView from '../components/video/LiveCameraView'
import Card from '../components/ui/Card'

const TIER_LABELS = {
  P1: { label: 'Face', color: '#00FF87' },
  P2: { label: 'Text', color: '#4ADE80' },
  P3: { label: 'Motion', color: '#F59E0B' },
  P4: { label: 'Object', color: '#818CF8' },
  P5: { label: 'Background', color: '#EF4444' },
}

export default function LivePage() {
  const [wsConnected, setWsConnected] = useState(false)

  return (
    // Override PageShell wsConnected here
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="relative">
          <Camera size={24} className="text-data-blue" />
          {wsConnected && <span className="live-dot absolute -top-1 -right-1" />}
        </div>
        <div>
          <h2 className="font-display text-xl font-bold text-text-primary">Live Camera Analysis</h2>
          <p className="text-text-muted text-sm mt-0.5">Real-time YOLO detection via WebSocket</p>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="flex items-center gap-3 py-4">
          <Shield size={20} className="text-tier-p1 shrink-0" />
          <div>
            <p className="text-xs text-text-muted">P1 Faces</p>
            <p className="text-sm font-semibold text-tier-p1">QP 18</p>
          </div>
        </Card>
        <Card className="flex items-center gap-3 py-4">
          <Eye size={20} className="text-tier-p3 shrink-0" />
          <div>
            <p className="text-xs text-text-muted">P3 Motion</p>
            <p className="text-sm font-semibold text-tier-p3">QP 26</p>
          </div>
        </Card>
        <Card className="flex items-center gap-3 py-4">
          <Activity size={20} className="text-accent-light shrink-0" />
          <div>
            <p className="text-xs text-text-muted">P5 Background</p>
            <p className="text-sm font-semibold text-accent-light">QP 40</p>
          </div>
        </Card>
      </div>

      {/* Camera view */}
      <Card>
        <LiveCameraView onConnectionChange={setWsConnected} />
      </Card>

      {/* Priority tier legend */}
      <Card>
        <Card.Header>
          <Card.Title>Priority Tier Legend</Card.Title>
          <Card.Subtitle>Colour coding used in bounding boxes and heatmap</Card.Subtitle>
        </Card.Header>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {Object.entries(TIER_LABELS).map(([tier, { label, color }]) => (
            <div
              key={tier}
              className="flex items-center gap-2.5 p-3 rounded-btn"
              style={{ background: `${color}11`, border: `1px solid ${color}33` }}
            >
              <div className="w-3 h-3 rounded-sm shrink-0" style={{ background: color }} />
              <div>
                <p className="text-xs font-mono font-bold" style={{ color }}>{tier}</p>
                <p className="text-xs text-text-muted">{label}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
