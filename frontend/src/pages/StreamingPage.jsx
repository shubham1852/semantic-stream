/**
 * pages/StreamingPage.jsx
 * HLS.js adaptive video player for the processed SemanticStream output.
 * Shows live QP assignments, buffer level, current metrics sidebar,
 * and the HLS manifest delivery via the backend stream endpoint.
 */

import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Activity, Layers, Wifi, Clock, Film } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import VideoPlayer from '../components/video/VideoPlayer'
import Card from '../components/ui/Card'
import { StatusBadge, TierBadge } from '../components/ui/Badge'
import { getStreamUrl, getStreamStatus } from '../api/stream'
import Spinner from '../components/ui/Spinner'

const QP_TIERS = [
  { tier: 'P1', label: 'Face',       qp: 18, color: '#00FF87' },
  { tier: 'P2', label: 'Text',       qp: 22, color: '#4ADE80' },
  { tier: 'P3', label: 'Motion',     qp: 26, color: '#F59E0B' },
  { tier: 'P4', label: 'Objects',    qp: 32, color: '#818CF8' },
  { tier: 'P5', label: 'Background', qp: 40, color: '#EF4444' },
]

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
  const [searchParams] = useSearchParams()
  const videoId = searchParams.get('videoId')

  const [streamReady, setStreamReady] = useState(false)
  const [checking, setChecking] = useState(true)
  const [bufferLevel, setBufferLevel] = useState(0)
  const [currentBitrate, setCurrentBitrate] = useState(0)

  /* Poll stream readiness */
  useEffect(() => {
    if (!videoId) { setChecking(false); return }
    let cancelled = false
    const check = async () => {
      try {
        const data = await getStreamStatus(videoId)
        if (!cancelled) {
          setStreamReady(data?.ready ?? false)
          setChecking(false)
        }
      } catch {
        if (!cancelled) setChecking(false)
      }
    }
    check()
    return () => { cancelled = true }
  }, [videoId])

  const streamUrl = videoId ? getStreamUrl(videoId) : null

  return (
    <PageShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-text-primary">
              Adaptive Stream Player
            </h1>
            <p className="text-sm text-text-muted mt-1">
              HLS.js playback of SemanticStream-encoded output with live QP assignments
            </p>
          </div>
          <StatusBadge status={streamReady ? 'done' : checking ? 'running' : 'idle'} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Player — left 2 cols */}
          <div className="lg:col-span-2 space-y-4">
            {checking ? (
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
                  {videoId ? 'Stream not ready — run an analysis first' : 'No video selected'}
                </p>
                <a href="/upload" className="btn-primary text-sm px-4 py-2 rounded-btn">
                  Upload & Analyze
                </a>
              </div>
            )}

            {/* Buffer level indicator */}
            <Card className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-text-muted">Buffer Level</span>
                <span className="font-mono text-sm text-accent-light">{bufferLevel.toFixed(1)}s</span>
              </div>
              <div className="w-full h-2 rounded-full" style={{ background: 'rgba(79,70,229,0.12)' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, (bufferLevel / 10) * 100)}%`,
                    background: bufferLevel < 4 ? 'linear-gradient(90deg,#EF4444,#F59E0B)' : 'linear-gradient(90deg,#4F46E5,#818CF8)',
                    boxShadow: bufferLevel < 4 ? '0 0 8px rgba(239,68,68,0.4)' : '0 0 8px rgba(79,70,229,0.4)',
                  }}
                />
              </div>
              <div className="flex justify-between text-xs text-text-muted mt-1">
                <span>0s</span>
                <span className="text-data-amber">4s emergency</span>
                <span>10s target</span>
              </div>
            </Card>
          </div>

          {/* Sidebar — metrics */}
          <div className="space-y-4">
            <Card className="p-4">
              <Card.Title>Live Metrics</Card.Title>
              <div className="mt-3">
                <MetricRow icon={Wifi}     label="Current Bitrate"  value={`${currentBitrate.toFixed(2)} Mbps`} color="#60A5FA" mono />
                <MetricRow icon={Activity} label="Buffer Health"    value={bufferLevel >= 4 ? 'Good' : 'Low'}   color={bufferLevel >= 4 ? '#00FF87' : '#EF4444'} />
                <MetricRow icon={Clock}    label="Encode Strategy"  value="SemanticStream" color="#00FF87" />
              </div>
            </Card>

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
    </PageShell>
  )
}
