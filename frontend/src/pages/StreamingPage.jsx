/**
 * pages/StreamingPage.jsx
 * Adaptive video player for SemanticStream-processed output.
 * - Session selector dropdown (fetched from GET /api/v1/history)
 * - VideoPlayer using /raw endpoint as primary stream
 * - Stream status indicator (polls /api/v1/stream/{id}/status)
 * - 4 stat chips: format, duration, SPQI, bitrate reduction
 * NOTE: No <PageShell> wrapper — App.jsx supplies it as a layout route.
 */

import { useState, useEffect, useCallback } from 'react'
import { Activity, Layers, Wifi, Clock, Film, ChevronDown, BarChart2 } from 'lucide-react'
import VideoPlayer from '../components/video/VideoPlayer'
import Card from '../components/ui/Card'
import Spinner from '../components/ui/Spinner'
import { StatusBadge, TierBadge } from '../components/ui/Badge'
import { getStreamStatus } from '../api/stream'
import { getReports } from '../api/reports'

const QP_TIERS = [
  { tier: 'P1', label: 'Face',       qp: 18, color: '#00FF87' },
  { tier: 'P2', label: 'High Pri',   qp: 22, color: '#4ADE80' },
  { tier: 'P3', label: 'Motion',     qp: 26, color: '#F59E0B' },
  { tier: 'P4', label: 'Objects',    qp: 32, color: '#818CF8' },
  { tier: 'P5', label: 'Background', qp: 40, color: '#EF4444' },
]

function StatChip({ icon: Icon, label, value, color = '#818CF8' }) {
  return (
    <div
      className="flex-1 min-w-0 rounded-card p-3 flex flex-col gap-1"
      style={{ background: `${color}0D`, border: `1px solid ${color}25` }}
    >
      <div className="flex items-center gap-1.5 text-xs text-text-muted">
        <Icon size={12} style={{ color }} />
        {label}
      </div>
      <div className="font-mono text-sm font-bold truncate" style={{ color }}>
        {value}
      </div>
    </div>
  )
}

function MetricRow({ icon: Icon, label, value, color = '#8892A4', mono = false }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border-subtle last:border-0">
      <div className="flex items-center gap-2 text-sm text-text-muted">
        <Icon size={14} style={{ color }} />
        {label}
      </div>
      <span
        className={`text-sm font-semibold ${mono ? 'font-mono' : ''}`}
        style={{ color: color !== '#8892A4' ? color : '#F0F0FF' }}
      >
        {value}
      </span>
    </div>
  )
}

export default function StreamingPage() {
  const [sessions, setSessions]       = useState([])
  const [loadingSessions, setLoadingSessions] = useState(true)
  const [selectedId, setSelectedId]   = useState('')
  const [streamStatus, setStreamStatus] = useState(null)
  const [checkingStream, setCheckingStream] = useState(false)

  /* Fetch completed sessions */
  useEffect(() => {
    getReports(100, 0)
      .then((data) => {
        const list = (data?.sessions ?? []).filter((s) => s.status === 'done' || s.spqi != null)
        setSessions(list)
        if (list.length > 0) setSelectedId(list[0].session_id)
      })
      .catch(() => setSessions([]))
      .finally(() => setLoadingSessions(false))
  }, [])

  /* Poll stream readiness for the selected session */
  const checkStream = useCallback(async (id) => {
    if (!id) return
    setCheckingStream(true)
    try {
      const data = await getStreamStatus(id)
      setStreamStatus(data)
    } catch {
      setStreamStatus(null)
    } finally {
      setCheckingStream(false)
    }
  }, [])

  useEffect(() => {
    setStreamStatus(null)
    if (selectedId) checkStream(selectedId)
  }, [selectedId, checkStream])

  const selectedSession = sessions.find((s) => s.session_id === selectedId) ?? null
  const streamReady     = streamStatus?.ready ?? false
  const streamType      = streamStatus?.stream_type ?? 'raw'

  /* Always use /raw as primary — VideoPlayer will fallback to HLS on error */
  const streamUrl = selectedId ? `/api/v1/stream/${selectedId}/raw` : null

  const duration    = selectedSession?.duration_seconds ?? null
  const spqi        = selectedSession?.spqi             ?? null
  const brReduction = selectedSession?.bitrate_reduction ?? null
  const format      = streamReady ? (streamType === 'hls' ? 'HLS' : 'MP4') : '—'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-text-primary">
            Adaptive Stream Player
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Play SemanticStream-processed output with QP tier assignments
          </p>
        </div>
        <StatusBadge status={streamReady ? 'done' : checkingStream ? 'running' : 'idle'} />
      </div>

      {/* ── Session Selector ────────────────────────────────── */}
      <Card className="p-4">
        <div className="flex items-center gap-3">
          <Film size={16} className="text-text-muted shrink-0" />
          <span className="text-sm text-text-muted font-medium shrink-0">Session:</span>
          {loadingSessions ? (
            <div className="flex items-center gap-2 text-sm text-text-muted">
              <Spinner size={14} />
              Loading sessions…
            </div>
          ) : sessions.length === 0 ? (
            <span className="text-sm text-text-muted">
              No completed sessions —{' '}
              <a href="/upload" className="text-accent-light hover:underline">
                upload and analyse a video
              </a>
            </span>
          ) : (
            <div className="relative flex-1 max-w-md">
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="w-full rounded-btn pl-3 pr-9 py-2 text-sm text-text-primary appearance-none outline-none cursor-pointer"
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                }}
              >
                {sessions.map((s) => (
                  <option key={s.session_id} value={s.session_id} style={{ background: '#0F1426' }}>
                    {s.filename ?? s.session_id.slice(0, 16) + '…'}
                    {s.spqi != null ? `  —  SPQI ${s.spqi.toFixed(4)}` : ''}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none"
              />
            </div>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Player — left 2 cols */}
        <div className="lg:col-span-2 space-y-4">
          {checkingStream ? (
            <div className="rounded-card flex items-center justify-center h-64 glass-card">
              <div className="flex flex-col items-center gap-3">
                <Spinner size={32} />
                <p className="text-sm text-text-muted">Checking stream availability…</p>
              </div>
            </div>
          ) : streamUrl && streamReady ? (
            <VideoPlayer src={streamUrl} className="w-full" />
          ) : (
            <div className="rounded-card flex flex-col items-center justify-center h-64 glass-card gap-4">
              <Film size={40} className="text-text-muted" />
              <p className="text-text-muted font-medium">
                {selectedId
                  ? 'Stream not ready — run an analysis first'
                  : 'No session selected'}
              </p>
              <a href="/upload" className="btn-primary text-sm px-4 py-2 rounded-btn">
                Upload &amp; Analyze
              </a>
            </div>
          )}

          {/* 4 Stat Chips */}
          {selectedSession && (
            <div className="flex gap-3">
              <StatChip
                icon={Wifi}
                label="Stream Format"
                value={format}
                color="#60A5FA"
              />
              <StatChip
                icon={Clock}
                label="Duration"
                value={duration != null ? `${Math.floor(duration / 60)}m ${Math.round(duration % 60)}s` : '—'}
                color="#818CF8"
              />
              <StatChip
                icon={Activity}
                label="SPQI Score"
                value={spqi != null ? spqi.toFixed(4) : '—'}
                color="#00FF87"
              />
              <StatChip
                icon={BarChart2}
                label="BR Reduction"
                value={brReduction != null ? `${brReduction.toFixed(1)}%` : '—'}
                color="#F59E0B"
              />
            </div>
          )}
        </div>

        {/* Sidebar — metrics */}
        <div className="space-y-4">
          {/* Session info */}
          {selectedSession && (
            <Card className="p-4">
              <Card.Title>Session Info</Card.Title>
              <div className="mt-3 space-y-0">
                <MetricRow icon={Film}     label="Video"    value={selectedSession.filename ?? '—'} />
                <MetricRow icon={Wifi}     label="Profile"  value={selectedSession.bandwidth_profile ?? '—'} />
                <MetricRow icon={Activity} label="SPQI"     value={spqi != null ? spqi.toFixed(4) : '—'} color="#00FF87" mono />
                <MetricRow icon={BarChart2} label="BR Saved" value={brReduction != null ? `${brReduction.toFixed(1)}%` : '—'} color="#F59E0B" mono />
              </div>
            </Card>
          )}

          {/* QP Tier Table */}
          <Card className="p-4">
            <Card.Title>QP Tier Assignments</Card.Title>
            <p className="text-xs text-text-muted mt-1 mb-3">
              Per-region quantization parameters applied during encoding
            </p>
            <div className="space-y-2">
              {QP_TIERS.map(({ tier, label, qp, color }) => (
                <div
                  key={tier}
                  className="flex items-center justify-between p-2 rounded-btn"
                  style={{ background: `${color}10`, border: `1px solid ${color}25` }}
                >
                  <div className="flex items-center gap-2">
                    <TierBadge tier={tier} />
                    <span className="text-sm text-text-muted">{label}</span>
                  </div>
                  <span className="font-mono text-sm font-semibold" style={{ color }}>
                    QP {qp}
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* How it works note */}
          <Card className="p-4" style={{ borderColor: 'rgba(79,70,229,0.3)' }}>
            <div className="flex items-start gap-2">
              <Layers size={16} className="text-accent-light mt-0.5 shrink-0" />
              <p className="text-xs text-text-muted leading-relaxed">
                SemanticStream encodes each frame with spatially non-uniform QP values.
                Faces receive QP 18 (maximum quality) while background regions are
                compressed at QP 40, achieving bitrate savings while protecting
                perceptually important content.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
