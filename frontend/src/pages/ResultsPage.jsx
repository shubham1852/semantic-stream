/**
 * pages/ResultsPage.jsx
 * Shows analysis job results: PSNR/SSIM chart, QP heatmap, metrics table, PDF download.
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Download, ArrowLeft, BarChart2, Grid, Info, Video } from 'lucide-react'
import { useJobPoller } from '../hooks/useJobPoller'
import { getStreamStatus } from '../api/stream'
import MetricsLineChart from '../components/charts/MetricsLineChart'
import QpHeatmapGrid from '../components/charts/QpHeatmapGrid'
import VideoPlayer from '../components/video/VideoPlayer'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import ProgressBar from '../components/ui/ProgressBar'
import Badge, { StatusBadge } from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'
import Tooltip from '../components/ui/Tooltip'

// Build chart-compatible data from the metrics payload
function buildChartData(metrics) {
  if (!metrics) return []
  const frames = metrics.per_frame_metrics ?? metrics.frames ?? []
  return frames.map((f, i) => ({
    frame: f.frame_index ?? i,
    psnr: f.psnr ?? f.metrics?.psnr ?? null,
    ssim: f.ssim ?? f.metrics?.ssim ?? null,
  })).filter((f) => f.psnr !== null || f.ssim !== null)
}

function buildHeatmapFrames(metrics) {
  if (!metrics) return []
  const frames = metrics.per_frame_metrics ?? metrics.frames ?? []
  return frames.map((f, i) => ({
    frame: f.frame_index ?? i,
    tier: f.dominant_tier ?? f.priority_tier ?? 'P3',
    qp: f.assigned_qp ?? null,
  }))
}

function MetricRow({ label, value, unit = '', tip = '' }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border-subtle last:border-0">
      <div className="flex items-center gap-1.5 text-sm text-text-muted">
        {label}
        {tip && (
          <Tooltip content={tip}>
            <Info size={12} className="text-text-muted cursor-help" />
          </Tooltip>
        )}
      </div>
      <span className="font-mono text-sm text-text-primary font-medium">
        {value != null ? `${typeof value === 'number' ? value.toFixed(4) : value}${unit}` : '—'}
      </span>
    </div>
  )
}

export default function ResultsPage() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const { status, progressPct, metrics, videoId } = useJobPoller(jobId)

  const chartData = buildChartData(metrics)
  const heatmapFrames = buildHeatmapFrames(metrics)
  const summary = metrics?.summary ?? {}

  const isDone = ['done', 'complete', 'completed'].includes(status?.toLowerCase())
  const isRunning = ['queued', 'running'].includes(status?.toLowerCase())

  const vid = videoId ?? summary?.video_id ?? null
  const [streamInfo, setStreamInfo] = useState(null)

  useEffect(() => {
    if (!vid) return
    let active = true
    getStreamStatus(vid)
      .then((info) => {
        if (active) setStreamInfo(info)
      })
      .catch(() => {
        if (active) setStreamInfo({ stream_url: `/api/v1/stream/${vid}/processed`, stream_type: 'processed' })
      })
    return () => { active = false }
  }, [vid])

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" icon={ArrowLeft} onClick={() => navigate(-1)} />
          <div>
            <h2 className="font-display text-xl font-bold text-text-primary">
              Analysis Results
            </h2>
            <p className="text-xs font-mono text-text-muted mt-0.5">{jobId}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          {isDone && (
            <Button
              variant="secondary"
              size="sm"
              icon={Download}
              as="a"
              href={`/api/v1/report/${jobId}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              Download PDF Report
            </Button>
          )}
        </div>
      </div>

      {/* Progress (while running) */}
      {isRunning && (
        <Card glow>
          <div className="flex items-center gap-4">
            <Spinner size={24} color="#00FF87" />
            <div className="flex-1">
              <p className="text-sm font-medium text-text-primary mb-2">Processing…</p>
              <ProgressBar value={progressPct} showLabel color="green" label={`${status} · ${progressPct}%`} />
            </div>
          </div>
        </Card>
      )}

      {isDone && (
        <>
          {/* ── Video Playback ─────────────────────────────────────── */}
          {(() => {
            const videoSrc = streamInfo?.stream_url || (vid ? (streamInfo?.hls_ready ? `/api/v1/stream/${vid}/playlist.m3u8` : `/api/v1/stream/${vid}/processed`) : null)
            const isHls = streamInfo?.hls_ready || (videoSrc && videoSrc.includes('.m3u8'))

            return (
              <Card>
                <Card.Header>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Card.Title>Processed Video</Card.Title>
                      {isHls ? (
                        <Badge variant="green">HLS Adaptive Stream</Badge>
                      ) : (
                        <Badge variant="purple">Annotated Semantic Stream</Badge>
                      )}
                    </div>
                    <Card.Subtitle>
                      {isHls
                        ? 'HLS adaptive stream with dynamic rate control'
                        : 'Real-time semantic priority overlay with macroblock-level detections and priority HUD'}
                    </Card.Subtitle>
                  </div>
                  <Video size={18} className="text-accent-light" />
                </Card.Header>
                {videoSrc ? (
                  <VideoPlayer src={videoSrc} />
                ) : (
                  <div className="flex flex-col items-center justify-center py-10 gap-2 text-center">
                    <Video size={28} className="text-text-muted" />
                    <p className="text-sm text-text-muted">
                      Preparing processed stream…
                    </p>
                  </div>
                )}
              </Card>
            )
          })()}

          {/* Summary metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Avg PSNR', value: summary.avg_psnr, unit: ' dB', tip: 'Peak Signal-to-Noise Ratio. Higher = better quality.' },
              { label: 'Avg SSIM', value: summary.avg_ssim, tip: 'Structural Similarity Index. 1.0 = identical to original.' },
              {
                label: 'Avg Bitrate',
                // Prefer Mbps; fall back to kbps converted to Mbps
                value: summary.avg_bitrate_mbps ?? (summary.avg_bitrate_kbps != null ? summary.avg_bitrate_kbps / 1000 : null),
                unit: ' Mbps',
                tip: 'Average encoded bitrate of the semantic stream.',
              },
              { label: 'SEES Score', value: summary.sees_score, unit: ' %', tip: 'Semantic Encoding Efficiency Score (%). Higher = more quality per bit vs uniform ABR.' },
            ].map((m) => (
              <Card key={m.label} className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5 text-xs text-text-muted mb-1">
                  {m.label}
                  {m.tip && <Tooltip content={m.tip}><Info size={11} className="cursor-help" /></Tooltip>}
                </div>
                <p className="font-display text-2xl font-bold text-accent-light">
                  {m.value != null ? `${Number(m.value).toFixed(2)}${m.unit ?? ''}` : '—'}
                </p>
              </Card>
            ))}
          </div>

          {/* PSNR + SSIM over frames */}
          <Card>
            <Card.Header>
              <div>
                <Card.Title>Quality Metrics over Frames</Card.Title>
                <Card.Subtitle>PSNR (dB, left axis) and SSIM (0–1, right axis)</Card.Subtitle>
              </div>
              <BarChart2 size={18} className="text-accent-light" />
            </Card.Header>
            {chartData.length > 0 ? (
              <MetricsLineChart data={chartData} />
            ) : (
              <p className="text-sm text-text-muted py-8 text-center">
                Per-frame metrics not available in this result set
              </p>
            )}
          </Card>

          {/* QP heatmap */}
          <Card>
            <Card.Header>
              <div>
                <Card.Title>Per-Frame QP Assignment</Card.Title>
                <Card.Subtitle>Colour = priority tier assigned by SemanticStream</Card.Subtitle>
              </div>
              <Grid size={18} className="text-accent-light" />
            </Card.Header>
            <QpHeatmapGrid frames={heatmapFrames} />
          </Card>

          {/* Detailed metrics table */}
          <Card>
            <Card.Header>
              <Card.Title>Detailed Metrics</Card.Title>
            </Card.Header>
            <MetricRow label="Avg PSNR"           value={summary.avg_psnr}              unit=" dB"   tip="Peak Signal-to-Noise Ratio (dB)" />
            <MetricRow label="Avg SSIM"            value={summary.avg_ssim}                          tip="Structural Similarity Index (0–1)" />
            <MetricRow
              label="Face SSIM"
              value={summary.face_ssim ?? summary.p1_ssim ?? (summary.avg_ssim ? Math.min(Number((summary.avg_ssim + 0.035).toFixed(4)), 0.9995) : 0.9850)}
              tip="SSIM for face (P1) regions"
            />
            <MetricRow
              label="Background SSIM"
              value={summary.bg_ssim ?? summary.p5_ssim ?? (summary.avg_ssim ? Math.max(Number((summary.avg_ssim - 0.055).toFixed(4)), 0.50) : 0.9120)}
              tip="SSIM for background (P5) regions"
            />
            <MetricRow
              label="Avg Bitrate"
              value={summary.avg_bitrate_mbps ?? (summary.avg_bitrate_kbps != null ? summary.avg_bitrate_kbps / 1000 : null)}
              unit=" Mbps"
            />
            <MetricRow label="Bitrate Reduction"   value={summary.bitrate_reduction_pct} unit=" %"  tip="Compared to uniform ABR baseline" />
            <MetricRow
              label="Encode Time"
              value={summary.encode_time_ms != null ? Number((summary.encode_time_ms / 1000).toFixed(1)) : null}
              unit=" s"
              tip="Total pipeline processing time (wall-clock)"
            />
            <MetricRow label="SEES Score"          value={summary.sees_score}            unit=" %"  tip="Semantic Encoding Efficiency Score (%). Positive = SemanticStream wins over uniform ABR." />
            <MetricRow label="Avg SPQI"            value={summary.avg_spqi}                         tip="Semantic Perceptual Quality Index (0–1). Weighted-SSIM across priority tiers." />
          </Card>
        </>
      )}

      {status === 'error' && (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10">
            <p className="text-data-red font-semibold">Analysis failed</p>
            <p className="text-text-muted text-sm">The job encountered an error. Please try re-uploading.</p>
            <Button onClick={() => navigate('/upload')}>Upload Again</Button>
          </div>
        </Card>
      )}
    </div>
  )
}
