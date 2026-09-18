// FILE: frontend/src/pages/LivePage.jsx
/**
 * pages/LivePage.jsx
 * ===================
 * Full Live Camera Analysis Page for SemanticStream — Phase 10 Upgrade.
 *
 * Requirements:
 *   - Two canvases side by side: left = annotated frame, right = heatmap. Each labeled. Both update at 10fps from WebSocket messages.
 *   - Priority legend bar always visible above canvases:
 *       ● P1 Humans #00FF50  ● P2 Animals #00C8FF  ● P3 Vehicles #008CFF  ● P4 Objects #003CFF  ■ P5 Background compressed
 *   - Detection pills row below canvases: for each unique detected class, show a colored pill [CLASS] ×N P[TIER] sorted P1 first.
 *   - Live stats row:
 *       * PCS Score (green >60%, amber 30–60%, red <30%)
 *       * Scene badge (DIALOGUE=green, ACTION=red, GENERAL=slate)
 *       * Latency badge (green <50ms, amber <150ms, red else)
 *       * Detection count
 *   - Bandwidth slider (0–100) sending bandwidth_factor (value/100) in every WebSocket message.
 *   - When bandwidth slider < 40, show red banner: "LOW BANDWIDTH MODE — Background compression maximized".
 *   - Rolling 30-frame latency chart preserved and fully functional.
 *   - All existing imports, hooks, and connections preserved.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Camera,
  CameraOff,
  Cpu,
  Eye,
  Flame,
  Layers,
  Radio,
  Scan,
  Shield,
  Sliders,
  TrendingDown,
  Zap,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceLine,
  Tooltip as RechartsTooltip,
} from 'recharts'
import LiveCameraView from '../components/video/LiveCameraView'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'

// Canonical priority tier metadata
const PRIORITY_TIERS = [
  { id: 1, label: 'P1 Humans', color: '#00FF50', bg: 'rgba(0, 255, 80, 0.15)', shape: '●' },
  { id: 2, label: 'P2 Animals', color: '#00C8FF', bg: 'rgba(0, 200, 255, 0.15)', shape: '●' },
  { id: 3, label: 'P3 Vehicles', color: '#008CFF', bg: 'rgba(0, 140, 255, 0.15)', shape: '●' },
  { id: 4, label: 'P4 Objects', color: '#003CFF', bg: 'rgba(0, 60, 255, 0.15)', shape: '●' },
  { id: 5, label: 'P5 Background compressed', color: '#505050', bg: 'rgba(80, 80, 80, 0.25)', shape: '■' },
]

const TIER_COLOR_MAP = {
  1: '#00FF50',
  2: '#00C8FF',
  3: '#008CFF',
  4: '#003CFF',
  5: '#505050',
}

const MAX_LATENCY_POINTS = 30

export default function LivePage({ onWsChange }) {
  const cameraRef = useRef(null)
  const leftCanvasRef = useRef(null)
  const rightCanvasRef = useRef(null)
  const frameCounterRef = useRef(0)

  // Stream & connection state
  const [isStreaming, setIsStreaming] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [bandwidth, setBandwidth] = useState(70) // 0-100 slider
  const [streamError, setStreamError] = useState(null)

  // Live frame metrics from WebSocket
  const [liveStats, setLiveStats] = useState({
    pcs_score: 0.0,
    scene_type: 'GENERAL',
    frame_latency_ms: 0,
    detections: [],
    priority_distribution: { P1: 0, P2: 0, P3: 0, P4: 0, P5_background: true },
  })

  // Rolling latency history for chart
  const [latencyHistory, setLatencyHistory] = useState([])

  // Toggle Camera
  const handleToggleCamera = async () => {
    setStreamError(null)
    if (isStreaming) {
      if (cameraRef.current) {
        cameraRef.current.stop()
      }
      setIsStreaming(false)
      setWsConnected(false)
    } else {
      try {
        if (cameraRef.current) {
          await cameraRef.current.start()
          setIsStreaming(true)
        }
      } catch (err) {
        setStreamError(err.message || 'Unable to access webcam. Please check permissions.')
        setIsStreaming(false)
      }
    }
  }

  // Draw annotated base64 frame onto left canvas
  const handleAnnotatedFrame = useCallback((frameB64) => {
    if (!frameB64) return
    const canvas = leftCanvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const img = new Image()
    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    }
    img.src = frameB64.startsWith('data:') ? frameB64 : `data:image/jpeg;base64,${frameB64}`
  }, [])

  // Draw heatmap base64 frame onto right canvas
  const handleHeatmapFrame = useCallback((frameB64) => {
    if (!frameB64) return
    const canvas = rightCanvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const img = new Image()
    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    }
    img.src = frameB64.startsWith('data:') ? frameB64 : `data:image/jpeg;base64,${frameB64}`
  }, [])

  // Process live statistics payload from server
  const handleStatsUpdate = useCallback((data) => {
    if (!data) return
    setLiveStats(data)

    const latency = Number(data.frame_latency_ms || 0)
    frameCounterRef.current += 1
    setLatencyHistory((prev) => {
      const next = [...prev, { idx: frameCounterRef.current, ms: latency }]
      return next.length > MAX_LATENCY_POINTS ? next.slice(-MAX_LATENCY_POINTS) : next
    })
  }, [])

  // Group unique detected classes for detection pills row
  const detectionPills = useMemo(() => {
    const rawDets = liveStats.detections || []
    if (!rawDets.length) return []

    const map = new Map()
    for (const d of rawDets) {
      const name = (d.class || 'object').toLowerCase()
      const priority = d.priority || 5
      const key = `${name}-${priority}`
      if (!map.has(key)) {
        map.set(key, { name, priority, count: 0, color: d.color || TIER_COLOR_MAP[priority] })
      }
      map.get(key).count += 1
    }

    // Sort P1 first, then P2, P3, P4, P5
    return Array.from(map.values()).sort((a, b) => a.priority - b.priority)
  }, [liveStats.detections])

  // Average latency
  const avgLatency = useMemo(() => {
    if (!latencyHistory.length) return null
    const sum = latencyHistory.reduce((acc, pt) => acc + pt.ms, 0)
    return (sum / latencyHistory.length).toFixed(1)
  }, [latencyHistory])

  // PCS Score presentation
  const pcsPercent = Math.round((liveStats.pcs_score || 0) * 100)
  const pcsColor =
    pcsPercent > 60 ? '#00FF50' : pcsPercent >= 30 ? '#F59E0B' : '#EF4444'

  // Scene badge styling
  const sceneType = (liveStats.scene_type || 'GENERAL').toUpperCase()
  const sceneColor =
    sceneType === 'DIALOGUE'
      ? '#00FF50'
      : sceneType === 'ACTION'
      ? '#EF4444'
      : '#64748B'

  // Latency badge styling
  const curLatency = liveStats.frame_latency_ms || 0
  const latencyBadgeColor =
    curLatency < 50 ? '#00FF50' : curLatency < 150 ? '#F59E0B' : '#EF4444'

  return (
    <div className="space-y-6 animate-slide-up">
      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="relative p-2.5 rounded-xl bg-accent/10 border border-accent/20">
            <Camera size={26} className="text-accent" />
            {isStreaming && wsConnected && (
              <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-[#00FF50] animate-pulse border-2 border-[#0D1117]" />
            )}
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-text-primary tracking-tight">
              Live Camera Semantic Analysis
            </h1>
            <p className="text-text-muted text-sm mt-0.5">
              10 FPS WebSocket Pipeline · Real-time Priority Heatmap · Background Degradation Simulation
            </p>
          </div>
        </div>

        {/* Start / Stop Controls */}
        <div className="flex items-center gap-3">
          <Button
            variant={isStreaming ? 'danger' : 'primary'}
            icon={isStreaming ? CameraOff : Camera}
            onClick={handleToggleCamera}
            className="px-5 py-2.5 font-semibold text-sm"
          >
            {isStreaming ? 'Stop Camera' : 'Start Camera'}
          </Button>
        </div>
      </div>

      {/* Error alert */}
      {streamError && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <AlertTriangle size={18} className="shrink-0" />
          <span>{streamError}</span>
        </div>
      )}

      {/* ── Bandwidth Control & Low-Bandwidth Red Banner ───────────────────── */}
      <Card className="p-4 space-y-3 bg-[#111622]/80 backdrop-blur-md border border-[#1E293B]">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <Sliders size={18} className="text-accent" />
            <span className="text-sm font-semibold text-text-primary">Simulated Bandwidth Factor</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-accent/10 text-accent font-bold">
              {bandwidth}% ({(bandwidth / 100).toFixed(2)})
            </span>
          </div>
          <span className="text-xs text-text-muted">
            Drag left to simulate throttled network & verify background compression
          </span>
        </div>

        <div className="flex items-center gap-4">
          <input
            type="range"
            min="5"
            max="100"
            step="1"
            value={bandwidth}
            onChange={(e) => setBandwidth(Number(e.target.value))}
            className="flex-1 h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-[#00FF50]"
          />
        </div>

        {/* Red banner when bandwidth slider < 40 */}
        {bandwidth < 40 && (
          <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-lg bg-red-600/20 border border-red-500/50 text-red-300 animate-pulse text-sm font-semibold">
            <AlertTriangle size={18} className="text-red-400 shrink-0" />
            <span>LOW BANDWIDTH MODE — Background compression maximized</span>
          </div>
        )}
      </Card>

      {/* ── Priority Legend Bar (ALWAYS VISIBLE ABOVE CANVASES) ────────────── */}
      <div className="flex items-center justify-center flex-wrap gap-4 px-4 py-2.5 rounded-xl bg-[#0F172A]/90 border border-slate-800 shadow-inner">
        {PRIORITY_TIERS.map((tier) => (
          <div key={tier.id} className="flex items-center gap-2 text-xs font-medium">
            <span style={{ color: tier.color }} className="text-sm leading-none font-bold">
              {tier.shape}
            </span>
            <span className="text-text-primary font-mono">{tier.label}</span>
            <span
              className="text-[10px] font-mono px-1.5 py-0.5 rounded"
              style={{ color: tier.color, background: tier.bg }}
            >
              {tier.color}
            </span>
          </div>
        ))}
      </div>

      {/* ── Live Stats Row ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* PCS Score Card */}
        <Card className="p-4 bg-[#111622]/90 border border-[#1E293B]">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1.5">
            <span className="flex items-center gap-1.5 font-medium">
              <Shield size={14} style={{ color: pcsColor }} />
              PCS Score
            </span>
            <span className="font-mono text-[10px] text-text-muted">Target &gt;60%</span>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="font-display text-2xl font-bold font-mono" style={{ color: pcsColor }}>
              {isStreaming ? `${pcsPercent}%` : '—'}
            </p>
            <span className="text-xs text-text-muted">priority coverage</span>
          </div>
        </Card>

        {/* Scene Badge Card */}
        <Card className="p-4 bg-[#111622]/90 border border-[#1E293B]">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1.5">
            <span className="flex items-center gap-1.5 font-medium">
              <Layers size={14} style={{ color: sceneColor }} />
              Scene Type
            </span>
            <span className="font-mono text-[10px] text-text-muted">AI Classifier</span>
          </div>
          <div className="mt-1">
            <span
              className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold font-mono tracking-wide"
              style={{
                color: sceneColor,
                background: `${sceneColor}20`,
                border: `1px solid ${sceneColor}50`,
              }}
            >
              {isStreaming ? sceneType : 'IDLE'}
            </span>
          </div>
        </Card>

        {/* Latency Badge Card */}
        <Card className="p-4 bg-[#111622]/90 border border-[#1E293B]">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1.5">
            <span className="flex items-center gap-1.5 font-medium">
              <Zap size={14} style={{ color: latencyBadgeColor }} />
              Frame Latency
            </span>
            <span className="font-mono text-[10px] text-text-muted">&lt;50ms Real-Time</span>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="font-display text-2xl font-bold font-mono" style={{ color: latencyBadgeColor }}>
              {isStreaming ? `${Math.round(curLatency)}ms` : '—'}
            </p>
            {avgLatency && (
              <span className="text-xs text-text-muted font-mono">avg {avgLatency}ms</span>
            )}
          </div>
        </Card>

        {/* Detection Count Card */}
        <Card className="p-4 bg-[#111622]/90 border border-[#1E293B]">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1.5">
            <span className="flex items-center gap-1.5 font-medium">
              <Activity size={14} className="text-[#00FF50]" />
              Detections
            </span>
            <span className="font-mono text-[10px] text-text-muted">YOLOv8n ONNX</span>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="font-display text-2xl font-bold font-mono text-text-primary">
              {isStreaming ? liveStats.detections?.length || 0 : 0}
            </p>
            <span className="text-xs text-text-muted">active targets</span>
          </div>
        </Card>
      </div>

      {/* ── Two Canvases Side-by-Side ──────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left Canvas: Annotated Frame */}
        <Card className="overflow-hidden border border-slate-800 bg-[#0B0F19] flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/80 bg-[#0F1524]">
            <div className="flex items-center gap-2">
              <Scan size={16} className="text-[#00FF50]" />
              <span className="text-sm font-semibold text-text-primary font-display">
                Annotated Semantic Feed
              </span>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#00FF50]/10 text-[#00FF50] border border-[#00FF50]/20">
              Boxes · Pills · HUD
            </span>
          </div>

          <div className="relative aspect-[4/3] bg-black flex items-center justify-center">
            <canvas
              ref={leftCanvasRef}
              width={640}
              height={480}
              className="w-full h-full object-contain"
            />
            {!isStreaming && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80 text-text-muted">
                <Camera size={38} className="text-slate-600" />
                <p className="text-sm font-medium">Camera is offline</p>
                <Button size="sm" variant="primary" onClick={handleToggleCamera}>
                  Start Live Camera
                </Button>
              </div>
            )}
          </div>
        </Card>

        {/* Right Canvas: Semantic Heatmap */}
        <Card className="overflow-hidden border border-slate-800 bg-[#0B0F19] flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/80 bg-[#0F1524]">
            <div className="flex items-center gap-2">
              <Flame size={16} className="text-[#00C8FF]" />
              <span className="text-sm font-semibold text-text-primary font-display">
                Semantic Priority Heatmap
              </span>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#00C8FF]/10 text-[#00C8FF] border border-[#00C8FF]/20">
              JET Background + Gaussian Bloomed ROI
            </span>
          </div>

          <div className="relative aspect-[4/3] bg-black flex items-center justify-center">
            <canvas
              ref={rightCanvasRef}
              width={640}
              height={480}
              className="w-full h-full object-contain"
            />
            {!isStreaming && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80 text-text-muted">
                <Flame size={38} className="text-slate-600" />
                <p className="text-sm font-medium">Heatmap generator waiting for feed</p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* ── Detection Pills Row Below Canvases ─────────────────────────────── */}
      <Card className="p-4 bg-[#0F172A]/70 border border-slate-800">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Eye size={15} className="text-accent" />
            <span className="text-xs font-semibold text-text-primary uppercase tracking-wider">
              Detected Targets by Priority (Sorted P1 First)
            </span>
          </div>
          <span className="text-xs font-mono text-text-muted">
            {detectionPills.length} distinct {detectionPills.length === 1 ? 'class' : 'classes'}
          </span>
        </div>

        {detectionPills.length > 0 ? (
          <div className="flex items-center gap-2 flex-wrap pt-1">
            {detectionPills.map((pill) => (
              <div
                key={`${pill.name}-${pill.priority}`}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-mono shadow-sm"
                style={{
                  borderColor: `${pill.color}60`,
                  backgroundColor: `${pill.color}15`,
                  color: pill.color,
                }}
              >
                <span className="font-bold uppercase tracking-wide">{pill.name}</span>
                <span className="opacity-80">×{pill.count}</span>
                <span
                  className="px-1.5 py-0.2 rounded text-[10px] font-black"
                  style={{
                    backgroundColor: pill.color,
                    color: '#000',
                  }}
                >
                  P{pill.priority}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-text-muted italic py-1">
            {isStreaming ? 'Scanning video frames for semantic objects…' : 'No active detections.'}
          </p>
        )}
      </Card>

      {/* ── Processing Latency Chart (Rolling 30 Frames) ──────────────────── */}
      <Card className="p-4 bg-[#111622]/90 border border-[#1E293B]">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-text-primary font-display flex items-center gap-2">
              <Cpu size={16} className="text-accent" />
              Pipeline Inference Latency (Rolling 30-Frame Window)
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              Target: &lt;50ms for seamless 20fps+ real-time processing
            </p>
          </div>
          {avgLatency && (
            <span className="text-xs font-mono px-2 py-1 rounded bg-slate-800 text-text-primary border border-slate-700">
              Avg: <strong className="text-[#00FF50]">{avgLatency} ms</strong>
            </span>
          )}
        </div>

        <div className="h-44 w-full">
          {latencyHistory.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={latencyHistory}>
                <XAxis dataKey="idx" hide />
                <YAxis
                  domain={[0, (dataMax) => Math.max(100, Math.ceil(dataMax * 1.2))]}
                  stroke="#475569"
                  tick={{ fill: '#94A3B8', fontSize: 11 }}
                  unit="ms"
                />
                <RechartsTooltip
                  contentStyle={{
                    backgroundColor: '#0F172A',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  formatter={(val) => [`${val} ms`, 'Latency']}
                />
                <ReferenceLine
                  y={50}
                  stroke="#00FF50"
                  strokeDasharray="3 3"
                  label={{ value: '50ms Target', fill: '#00FF50', fontSize: 10, position: 'insideTopRight' }}
                />
                <Line
                  type="monotone"
                  dataKey="ms"
                  stroke="#00C8FF"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs text-text-muted">
              {isStreaming ? 'Collecting latency telemetry…' : 'Start camera to view live latency chart.'}
            </div>
          )}
        </div>
      </Card>

      {/* Headless webcam capture component */}
      <LiveCameraView
        ref={cameraRef}
        bandwidthFactor={bandwidth / 100}
        onConnectionChange={(connected) => {
          setWsConnected(connected)
          onWsChange?.(connected)
        }}
        onAnnotatedFrame={handleAnnotatedFrame}
        onHeatmapFrame={handleHeatmapFrame}
        onStatsUpdate={handleStatsUpdate}
      />
    </div>
  )
}
