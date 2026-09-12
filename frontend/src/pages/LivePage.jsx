/**
 * pages/LivePage.jsx
 * Full live camera analysis with real-time detection panel.
 *
 * IMPROVEMENTS (2026-09-12):
 *   1. Mock Mode Warning Banner — amber dismissible banner when ONNX not loaded
 *   2. Processing Latency Chart — rolling 30-frame Recharts LineChart
 *   3. Detection Count Badge — live count of bounding boxes in current frame
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Camera, Eye, Activity, Shield } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer,
  ReferenceLine, Tooltip as RechartsTooltip,
} from 'recharts'
import LiveCameraView from '../components/video/LiveCameraView'
import Card from '../components/ui/Card'

const TIER_LABELS = {
  P1: { label: 'Face', color: '#00FF87' },
  P2: { label: 'Text', color: '#4ADE80' },
  P3: { label: 'Motion', color: '#F59E0B' },
  P4: { label: 'Object', color: '#818CF8' },
  P5: { label: 'Background', color: '#EF4444' },
}

const MAX_LATENCY_POINTS = 30

export default function LivePage() {
  const [wsConnected, setWsConnected] = useState(false)

  // ── Improvement 1: Mock Mode Warning Banner ──────────────────────────────
  const [showMockWarning, setShowMockWarning] = useState(false)

  useEffect(() => {
    fetch('/api/v1/demo/status')
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.ai_engine?.mode === 'MOCK_FALLBACK') {
          setShowMockWarning(true)
        }
      })
      .catch(() => {})
  }, [])

  // ── Improvement 2: Processing Latency Chart ──────────────────────────────
  const [latencyHistory, setLatencyHistory] = useState([])
  const frameIndexRef = useRef(0)

  // ── Improvement 3: Detection Count Badge ────────────────────────────────
  const [detectionCount, setDetectionCount] = useState(0)

  const handleFrameReceived = useCallback((frame) => {
    // Update rolling latency history
    const ms = frame?.processing_ms ?? frame?.processing_time_ms ?? 0
    frameIndexRef.current += 1
    setLatencyHistory((prev) => {
      const next = [...prev, { idx: frameIndexRef.current, ms: Number(ms.toFixed(1)) }]
      return next.length > MAX_LATENCY_POINTS ? next.slice(-MAX_LATENCY_POINTS) : next
    })

    // Update detection count
    const count = Array.isArray(frame?.detections) ? frame.detections.length : 0
    setDetectionCount(count)
  }, [])

  return (
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

      {/* ── Improvement 1: Mock Mode Warning Banner ── */}
      {showMockWarning && (
        <div className="mb-4 flex items-center gap-3 px-4 py-3 rounded-lg
                        bg-amber-500/10 border border-amber-500/30">
          <span className="text-amber-400 text-lg">⚠</span>
          <div>
            <p className="text-sm font-semibold text-amber-300">
              Running in Mock Mode
            </p>
            <p className="text-xs text-amber-400/70">
              ONNX model not found. Detections are simulated.
              Run: python backend/models/export_onnx.py to enable real AI inference.
            </p>
          </div>
          <button
            onClick={() => setShowMockWarning(false)}
            className="ml-auto text-amber-400 hover:text-amber-300 text-lg"
            aria-label="Dismiss mock mode warning"
          >
            ✕
          </button>
        </div>
      )}

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

        {/* ── Improvement 3: Detection Count Badge ── */}
        <Card className="flex items-center gap-3 py-4">
          <Activity
            size={20}
            className="shrink-0"
            style={{ color: detectionCount > 0 ? '#00FF87' : '#F59E0B' }}
          />
          <div>
            <p className="text-xs text-text-muted">Detections</p>
            <p
              className="text-sm font-semibold font-mono"
              style={{ color: detectionCount > 0 ? '#00FF87' : '#F59E0B' }}
            >
              {detectionCount} {detectionCount === 1 ? 'object' : 'objects'}
            </p>
          </div>
        </Card>
      </div>

      {/* Camera view */}
      <Card>
        <LiveCameraView
          onConnectionChange={setWsConnected}
          onFrameReceived={handleFrameReceived}
        />
      </Card>

      {/* ── Improvement 2: Processing Latency Chart ── */}
      {latencyHistory.length > 0 && (
        <Card>
          <Card.Header>
            <div>
              <Card.Title>Processing Latency (ms/frame)</Card.Title>
              <Card.Subtitle>
                Rolling last {MAX_LATENCY_POINTS} frames · dashed red = 50 ms target
              </Card.Subtitle>
            </div>
            <Activity size={18} className="text-accent-light" />
          </Card.Header>
          <div style={{ height: 160 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={latencyHistory} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <XAxis
                  dataKey="idx"
                  tick={{ fontSize: 10, fill: '#6B7280' }}
                  tickLine={false}
                  axisLine={false}
                  label={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#6B7280' }}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 'auto']}
                />
                <RechartsTooltip
                  contentStyle={{
                    background: '#111827',
                    border: '1px solid rgba(79,70,229,0.3)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(v) => [`${v} ms`, 'Latency']}
                  labelFormatter={(i) => `Frame ${i}`}
                />
                {/* 50 ms target reference line */}
                <ReferenceLine
                  y={50}
                  stroke="#EF4444"
                  strokeDasharray="4 3"
                  strokeOpacity={0.7}
                />
                <Line
                  type="monotone"
                  dataKey="ms"
                  stroke="#818CF8"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

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
