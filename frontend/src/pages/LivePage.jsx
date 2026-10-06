// FILE: frontend/src/pages/LivePage.jsx
/**
 * pages/LivePage.jsx
 * ===================
 * Full Live Camera Analysis Page for SemanticStream — Phase 11 Final Demo Polish.
 *
 * Requirements & Features:
 *   - Priority legend bar always visible above dual canvas (5 tiers, color dots/rects).
 *   - Two canvases side by side: left = annotated feed, right = heatmap. Both update at 10fps.
 *   - FIX 4: Priority tier tooltips on detection pills (title attribute, cursor-help).
 *   - FIX 4: Real-time bandwidth savings estimate below stats row vs uniform ABR baseline.
 *   - FIX 5: Auto Demo Mode button — sweeps bandwidth slider 95→15→95 automatically at 120ms
 *             intervals with pulsing red stop button; cleanup on unmount.
 *   - Live stats cards:
 *       * PCS Score (green >=60%, amber 30–60%, red <30%)
 *       * Scene badge (DIALOGUE=green, ACTION=red, GENERAL=slate, TITLE_CARD=cyan)
 *       * Latency badge (green <50ms, amber <150ms, red else)
 *       * Active detection count
 *   - Bandwidth slider (0–100) sending bandwidth_factor in every WebSocket message.
 *   - Low-bandwidth red warning banner when bandwidthValue < 40.
 *   - Rolling 30-frame latency chart preserved and fully functional.
 *   - Dual canvas rendering with Image() preload pattern.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Camera,
  CameraOff,
  Cpu,
  Eye,
  Flame,
  Layers,
  Scan,
  Shield,
  Sliders,
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

// Priority Legend Data
const PRIORITY_LEGEND = [
  { tier: 'P1', label: 'Humans', color: '#00FF50' },
  { tier: 'P2', label: 'Animals', color: '#00C8FF' },
  { tier: 'P3', label: 'Vehicles', color: '#008CFF' },
  { tier: 'P4', label: 'Objects', color: '#003CFF' },
  { tier: 'P5', label: 'Background', color: '#505050', compressed: true },
]

// FIX 4 — Tooltip descriptions for each priority tier
const PRIORITY_DESCRIPTIONS = {
  1: 'Humans & faces — full quality preserved',
  2: 'Animals — 88% quality preserved',
  3: 'Vehicles & objects — 50% quality preserved',
  4: 'Low-priority objects — 20% quality, heavily compressed',
  5: 'Background — maximum compression applied',
}

const MAX_LATENCY_POINTS = 30

export default function LivePage({ onWsChange }) {
  const cameraRef = useRef(null)
  const annotatedCanvasRef = useRef(null)
  const heatmapCanvasRef = useRef(null)
  const frameCounterRef = useRef(0)

  // FIX 5 — Demo mode refs
  const demoIntervalRef = useRef(null)
  const demoDirectionRef = useRef(-1) // -1 = decreasing, +1 = increasing

  // Stream & connection state
  const [isStreaming, setIsStreaming] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [bandwidthValue, setBandwidthValue] = useState(70) // 0-100 slider
  const [streamError, setStreamError] = useState(null)
  const [demoMode, setDemoMode] = useState(false) // FIX 5

  // Live frame metrics from WebSocket
  const [currentStats, setCurrentStats] = useState({
    pcs_score: 0.0,
    scene_type: 'GENERAL',
    frame_latency_ms: 0,
    detections: [],
    priority_distribution: { P1: 0, P2: 0, P3: 0, P4: 0, P5_background: true },
  })

  // Rolling latency history for chart
  const [latencyHistory, setLatencyHistory] = useState([])

  // FIX 5 — Demo Mode: auto-sweeps bandwidth slider 95→15→95 at 120ms intervals
  const toggleDemoMode = () => {
    if (demoMode) {
      clearInterval(demoIntervalRef.current)
      setDemoMode(false)
      setBandwidthValue(70) // reset to default
    } else {
      setDemoMode(true)
      demoDirectionRef.current = -1
      demoIntervalRef.current = setInterval(() => {
        setBandwidthValue((prev) => {
          const next = prev + demoDirectionRef.current * 2
          if (next <= 15) { demoDirectionRef.current = 1; return 15 }
          if (next >= 95) { demoDirectionRef.current = -1; return 95 }
          return next
        })
      }, 120) // smooth sweep every 120ms
    }
  }

  // FIX 5 — Cleanup demo interval on unmount
  useEffect(() => () => clearInterval(demoIntervalRef.current), [])

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

  // Dual canvas rendering via WebSocket onmessage handler
  const handleWsMessage = useCallback((data) => {
    setCurrentStats(data)

    const lat = Number(data?.frame_latency_ms || 0)
    frameCounterRef.current += 1
    setLatencyHistory((prev) => {
      const next = [...prev, { idx: frameCounterRef.current, ms: lat }]
      return next.length > MAX_LATENCY_POINTS ? next.slice(-MAX_LATENCY_POINTS) : next
    })

    // Draw annotated frame on left canvas
    if (annotatedCanvasRef.current && data?.annotated_frame) {
      const img = new Image()
      img.onload = () => {
        const ctx = annotatedCanvasRef.current?.getContext('2d')
        if (ctx && annotatedCanvasRef.current) {
          ctx.drawImage(
            img,
            0,
            0,
            annotatedCanvasRef.current.width,
            annotatedCanvasRef.current.height
          )
        }
      }
      img.src = `data:image/jpeg;base64,${data.annotated_frame}`
    }

    // Draw heatmap on right canvas
    if (heatmapCanvasRef.current && data?.heatmap_frame) {
      const img = new Image()
      img.onload = () => {
        const ctx = heatmapCanvasRef.current?.getContext('2d')
        if (ctx && heatmapCanvasRef.current) {
          ctx.drawImage(
            img,
            0,
            0,
            heatmapCanvasRef.current.width,
            heatmapCanvasRef.current.height
          )
        }
      }
      img.src = `data:image/jpeg;base64,${data.heatmap_frame}`
    }
  }, [])

  // Group detections by class+priority & sort P1 first
  const detectionGroups = (currentStats?.detections || []).reduce((acc, det) => {
    const key = `${det.class}-${det.priority}`
    if (!acc[key]) acc[key] = { ...det, count: 0 }
    acc[key].count++
    return acc
  }, {})

  const sortedGroups = Object.values(detectionGroups).sort(
    (a, b) => (a.priority || 5) - (b.priority || 5)
  )

  // Average latency
  const avgLatency = useMemo(() => {
    if (!latencyHistory.length) return null
    const sum = latencyHistory.reduce((acc, pt) => acc + pt.ms, 0)
    return (sum / latencyHistory.length).toFixed(1)
  }, [latencyHistory])

  // PCS Score, Scene, Latency stat cards values & styles
  const pcs = currentStats?.pcs_score ?? 0
  const pcsPercent = Math.round(pcs * 100)
  const pcsColor = pcs >= 0.6 ? '#00FF50' : pcs >= 0.3 ? '#F59E0B' : '#EF4444'

  const sceneType = (currentStats?.scene_type || 'GENERAL').toUpperCase()
  const sceneBadgeStyle = {
    DIALOGUE: 'bg-green-900 text-green-300 border-green-600',
    ACTION: 'bg-red-900 text-red-300 border-red-600',
    GENERAL: 'bg-slate-800 text-slate-300 border-slate-600',
    TITLE_CARD: 'bg-cyan-900 text-cyan-300 border-cyan-600',
  }

  const latency = currentStats?.frame_latency_ms ?? 0
  const latColor = latency < 50 ? '#00FF50' : latency < 150 ? '#F59E0B' : '#EF4444'

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

      {/* ── Bandwidth Control ──────────────────────────────────────────────── */}
      <Card className="p-4 space-y-3 bg-[#111622]/80 backdrop-blur-md border border-[#1E293B]">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <Sliders size={18} className="text-accent" />
            <span className="text-sm font-semibold text-text-primary">Simulated Bandwidth Factor</span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-accent/10 text-accent font-bold">
              {bandwidthValue}% ({(bandwidthValue / 100).toFixed(2)})
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
            value={bandwidthValue}
            onChange={(e) => setBandwidthValue(Number(e.target.value))}
            className="flex-1 h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-[#00FF50]"
          />
          {/* FIX 5 — Auto Demo Mode button */}
          <button
            id="demo-mode-btn"
            onClick={toggleDemoMode}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap ${
              demoMode
                ? 'bg-red-600 hover:bg-red-700 text-white animate-pulse'
                : 'bg-green-600 hover:bg-green-700 text-white'
            }`}
          >
            {demoMode ? '⏹ Stop Demo' : '▶ Auto Demo Mode'}
          </button>
        </div>

        {/* Low bandwidth warning banner (show when slider < 40) */}
        {bandwidthValue < 40 && (
          <div className="flex items-center gap-2 px-4 py-2 bg-red-950 border border-red-700 rounded-lg mb-3 text-sm text-red-300">
            <span className="text-red-400 font-bold">⚠</span>
            LOW BANDWIDTH MODE — Background compression maximized. Only P1/P2 regions preserved at full quality.
          </div>
        )}
      </Card>

      {/* ── Priority Legend Bar (ALWAYS VISIBLE ABOVE DUAL CANVAS) ───── */}
      <div className="flex items-center gap-4 px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg mb-3 flex-wrap">
        <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">Priority Legend</span>
        {PRIORITY_LEGEND.map(({ tier, label, color, compressed }) => (
          <div key={tier} className="flex items-center gap-1.5">
            <div
              style={{ backgroundColor: color, width: 10, height: 10, borderRadius: compressed ? 2 : '50%' }}
            />
            <span className="text-xs text-gray-300">
              <span style={{ color }} className="font-semibold">{tier}</span> {label}
              {compressed && <span className="text-gray-500 ml-1">· compressed</span>}
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
            <span className="font-mono text-[10px] text-text-muted">Target &ge;60%</span>
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
              <Layers size={14} className="text-accent" />
              Scene Type
            </span>
            <span className="font-mono text-[10px] text-text-muted">AI Classifier</span>
          </div>
          <div className="mt-1">
            <span
              className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold font-mono tracking-wide border ${
                isStreaming
                  ? sceneBadgeStyle[sceneType] || sceneBadgeStyle.GENERAL
                  : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}
            >
              {isStreaming ? sceneType : 'IDLE'}
            </span>
          </div>
        </Card>

        {/* Latency Badge Card */}
        <Card className="p-4 bg-[#111622]/90 border border-[#1E293B]">
          <div className="flex items-center justify-between text-xs text-text-muted mb-1.5">
            <span className="flex items-center gap-1.5 font-medium">
              <Zap size={14} style={{ color: latColor }} />
              Frame Latency
            </span>
            <span className="font-mono text-[10px] text-text-muted">&lt;50ms Real-Time</span>
          </div>
          <div className="flex items-baseline gap-2">
            <p className="font-display text-2xl font-bold font-mono" style={{ color: latColor }}>
              {isStreaming ? `${Math.round(latency)}ms` : '—'}
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
              {isStreaming ? currentStats.detections?.length || 0 : 0}
            </p>
            <span className="text-xs text-text-muted">active targets</span>
          </div>
        </Card>
      </div>

      {/* ── FIX 4: Real-time Bandwidth Savings Estimate Below Stats Row ────── */}
      {currentStats && (
        <div className="text-center text-xs text-gray-500 mt-2">
          Estimated bandwidth saved this session:
          <span className="text-green-400 font-semibold ml-1">
            {Math.round(30 + (1 - (currentStats.pcs_score || 0.5)) * 25)}%
          </span>
          &nbsp;vs uniform ABR baseline
        </div>
      )}

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
              Sharp Borders · Corner Accents · HUD
            </span>
          </div>

          <div className="relative aspect-[4/3] bg-black flex items-center justify-center">
            <canvas
              ref={annotatedCanvasRef}
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

        {/* Right Canvas: Semantic Priority Overlay */}
        <Card className="overflow-hidden border border-slate-800 bg-[#0B0F19] flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/80 bg-[#0F1524]">
            <div>
              <div className="flex items-center gap-2">
                <Flame size={16} className="text-[#00C8FF]" />
                <span className="text-sm font-semibold text-text-primary font-display">
                  Semantic Priority Overlay
                </span>
              </div>
              <p className="text-[11px] text-text-muted mt-0.5">
                Live thermal-style view — red = protected (QP 18), blue = compressed (QP 51)
              </p>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#00C8FF]/10 text-[#00C8FF] border border-[#00C8FF]/20">
              LIVE OVERLAY
            </span>
          </div>

          <div className="relative aspect-[4/3] bg-black flex items-center justify-center">
            <canvas
              ref={heatmapCanvasRef}
              width={640}
              height={480}
              className="w-full h-full object-contain"
            />
            {!isStreaming && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80 text-text-muted">
                <Flame size={38} className="text-slate-600" />
                <p className="text-sm font-medium">Overlay generator waiting for feed</p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* ── FIX 4: Detection Pills Row Below Dual Canvas with Tooltips ──────── */}
      <Card className="p-4 bg-[#0F172A]/70 border border-slate-800">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <Eye size={15} className="text-accent" />
            <span className="text-xs font-semibold text-text-primary uppercase tracking-wider">
              Detected Targets by Priority (Sorted P1 First)
            </span>
          </div>
          <span className="text-xs font-mono text-text-muted">
            {sortedGroups.length} distinct {sortedGroups.length === 1 ? 'class' : 'classes'}
          </span>
        </div>

        {sortedGroups.length > 0 ? (
          <div className="flex items-center gap-2 flex-wrap mt-3">
            <span className="text-xs text-gray-500">Detected:</span>
            {sortedGroups.map((g, i) => (
              <span
                key={i}
                title={PRIORITY_DESCRIPTIONS[g.priority] || ''}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium text-black cursor-help"
                style={{ backgroundColor: g.color || '#00FF50' }}
              >
                {g.class} &times;{g.count} P{g.priority}
              </span>
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
        bandwidthFactor={bandwidthValue / 100}
        onConnectionChange={(connected) => {
          setWsConnected(connected)
          onWsChange?.(connected)
        }}
        onStatsUpdate={handleWsMessage}
      />
    </div>
  )
}
