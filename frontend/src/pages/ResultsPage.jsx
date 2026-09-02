/**
 * pages/ResultsPage.jsx
 * Shows analysis job results: PSNR/SSIM chart, QP heatmap, metrics table, PDF download.
 */

import { useParams, useNavigate } from 'react-router-dom'
import { Download, ArrowLeft, BarChart2, Grid, Info } from 'lucide-react'
import { useJobPoller } from '../hooks/useJobPoller'
import MetricsLineChart from '../components/charts/MetricsLineChart'
import QpHeatmapGrid from '../components/charts/QpHeatmapGrid'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import ProgressBar from '../components/ui/ProgressBar'
import { StatusBadge } from '../components/ui/Badge'
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
  const { status, progressPct, metrics } = useJobPoller(jobId)

  const chartData = buildChartData(metrics)
  const heatmapFrames = buildHeatmapFrames(metrics)
  const summary = metrics?.summary ?? metrics ?? {}

  const isDone = ['done', 'complete', 'completed'].includes(status?.toLowerCase())
  const isRunning = ['queued', 'running'].includes(status?.toLowerCase())

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
          {/* Summary metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Avg PSNR', value: summary.avg_psnr, unit: ' dB', tip: 'Peak Signal-to-Noise Ratio. Higher = better quality.' },
              { label: 'Avg SSIM', value: summary.avg_ssim, tip: 'Structural Similarity Index. 1.0 = identical to original.' },
              { label: 'Avg Bitrate', value: summary.avg_bitrate_mbps, unit: ' Mbps', tip: 'Average encoded bitrate.' },
              { label: 'SEES Score', value: summary.sees_score, tip: 'Semantic Encoding Efficiency Score. Higher = better semantic efficiency.' },
            ].map((m) => (
              <Card key={m.label} className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5 text-xs text-text-muted mb-1">
                  {m.label}
                  {m.tip && <Tooltip content={m.tip}><Info size={11} className="cursor-help" /></Tooltip>}
                </div>
                <p className="font-display text-2xl font-bold text-accent-light">
                  {m.value != null ? `${Number(m.value).toFixed(3)}${m.unit ?? ''}` : '—'}
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
            <MetricRow label="Face SSIM"           value={summary.face_ssim ?? summary.p1_ssim}      tip="SSIM for face (P1) regions" />
            <MetricRow label="Background SSIM"     value={summary.bg_ssim ?? summary.p5_ssim}        tip="SSIM for background (P5) regions" />
            <MetricRow label="Avg Bitrate"         value={summary.avg_bitrate_mbps}     unit=" Mbps" />
            <MetricRow label="Bitrate Reduction"   value={summary.bitrate_reduction_pct} unit="%"   tip="Compared to uniform ABR baseline" />
            <MetricRow label="Encode Time"         value={summary.encode_time_ms}        unit=" ms"  />
            <MetricRow label="SEES Score"          value={summary.sees_score}                        tip="Semantic Encoding Efficiency Score" />
            <MetricRow label="Avg SPQI"            value={summary.avg_spqi}                          tip="Semantic Perceptual Quality Index" />
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
