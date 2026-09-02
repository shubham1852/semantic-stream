/**
 * pages/ExperimentPage.jsx
 * Configure and run a 3-strategy comparison experiment.
 */

import { useEffect, useState } from 'react'
import { FlaskConical, Trophy } from 'lucide-react'
import { getHistory } from '../api/videos'
import { getBandwidthProfiles } from '../api/bandwidth'
import { startExperiment } from '../api/experiments'
import { useExperimentPoller } from '../hooks/useExperimentPoller'
import useAppStore from '../store/useAppStore'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Spinner from '../components/ui/Spinner'
import StrategyRadarChart from '../components/charts/StrategyRadarChart'
import BitrateBarChart from '../components/charts/BitrateBarChart'

const STRATEGIES = [
  { id: 'uniform_abr',    label: 'Uniform ABR',    color: 'text-data-red',   desc: 'Baseline: same QP for all regions' },
  { id: 'static_roi',     label: 'Static ROI',     color: 'text-data-amber', desc: 'Face region boosted, rest uniform' },
  { id: 'semanticstream', label: 'SemanticStream',  color: 'text-data-green', desc: 'Dynamic YOLO-driven per-tier QP' },
]

const STRATEGY_LABELS = {
  uniform_abr: 'Uniform ABR',
  static_roi: 'Static ROI',
  semanticstream: 'SemanticStream',
}

export default function ExperimentPage() {
  const [sessions, setSessions] = useState([])
  const [profiles, setProfiles] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const exp = useAppStore((s) => s.experiment)
  const setExperimentConfig = useAppStore((s) => s.setExperimentConfig)
  const setExperimentRunning = useAppStore((s) => s.setExperimentRunning)
  const setExperimentDone = useAppStore((s) => s.setExperimentDone)
  const addToast = useAppStore((s) => s.addToast)

  const { status, results, winner } = useExperimentPoller(exp.experimentId)

  // Sync results to store
  useEffect(() => {
    if (status === 'done' && results) {
      setExperimentDone(results)
    }
  }, [status, results, setExperimentDone])

  useEffect(() => {
    Promise.all([
      getHistory(50, 0).then((d) => setSessions(d?.sessions ?? [])).catch(() => {}),
      getBandwidthProfiles().then((d) => setProfiles(d?.profiles ?? {})).catch(() => {}),
    ])
  }, [])

  const toggleStrategy = (id) => {
    const cur = exp.config.strategies
    setExperimentConfig({
      strategies: cur.includes(id) ? cur.filter((s) => s !== id) : [...cur, id],
    })
  }

  const handleRun = async () => {
    if (!exp.config.videoId) {
      addToast({ type: 'warning', title: 'Select a video', message: 'Choose a previously uploaded video' })
      return
    }
    if (exp.config.strategies.length < 2) {
      addToast({ type: 'warning', title: 'Select at least 2 strategies' })
      return
    }
    setSubmitting(true)
    try {
      const data = await startExperiment(exp.config)
      setExperimentRunning(data.experiment_id)
      addToast({ type: 'success', title: 'Experiment started', message: data.experiment_id?.slice(0, 8) })
    } catch (err) {
      addToast({ type: 'error', title: 'Failed to start experiment', message: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  const isRunning = status === 'running'
  const isDone = status === 'done'

  // Build bitrate chart data from results
  const bitrateData = isDone && results
    ? Object.entries(results).map(([strategy, m]) => ({
        strategy,
        bitrate: m.avg_bitrate_mbps ?? 0,
      }))
    : []

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex items-center gap-3">
        <FlaskConical size={24} className="text-data-green" />
        <div>
          <h2 className="font-display text-xl font-bold text-text-primary">Strategy Comparison</h2>
          <p className="text-text-muted text-sm mt-0.5">Run all 3 strategies on the same video and compare quality/efficiency</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Config panel */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <Card.Header><Card.Title>Configuration</Card.Title></Card.Header>

            {/* Video selector */}
            <div className="space-y-1.5 mb-4">
              <label className="text-xs font-medium text-text-muted uppercase tracking-widest">Video</label>
              <select
                className="select-field"
                value={exp.config.videoId}
                onChange={(e) => setExperimentConfig({ videoId: e.target.value })}
              >
                <option value="">— Select uploaded video —</option>
                {sessions.map((s) => (
                  <option key={s.video_id ?? s.id} value={s.video_id ?? s.id}>
                    {s.filename ?? s.video_id ?? s.id}
                  </option>
                ))}
              </select>
            </div>

            {/* Bandwidth profile */}
            <div className="space-y-1.5 mb-5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-widest">Bandwidth Profile</label>
              <select
                className="select-field"
                value={exp.config.bandwidthProfile}
                onChange={(e) => setExperimentConfig({ bandwidthProfile: e.target.value })}
              >
                {Object.keys(profiles).map((p) => (
                  <option key={p} value={p}>{p.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>

            {/* Strategy toggles */}
            <div className="space-y-2 mb-5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-widest">Strategies</label>
              {STRATEGIES.map((s) => {
                const active = exp.config.strategies.includes(s.id)
                return (
                  <button
                    key={s.id}
                    onClick={() => toggleStrategy(s.id)}
                    className={`w-full flex items-start gap-3 p-3 rounded-btn text-left transition-all duration-150 border ${
                      active
                        ? 'border-accent/40 bg-accent/8'
                        : 'border-border-subtle hover:border-accent/20 hover:bg-white/3'
                    }`}
                  >
                    <div className={`w-4 h-4 mt-0.5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${active ? 'bg-accent border-accent' : 'border-border-subtle'}`}>
                      {active && <span className="text-white text-xs font-bold">✓</span>}
                    </div>
                    <div>
                      <p className={`text-sm font-medium ${s.color}`}>{s.label}</p>
                      <p className="text-xs text-text-muted mt-0.5">{s.desc}</p>
                    </div>
                  </button>
                )
              })}
            </div>

            <Button loading={submitting || isRunning} onClick={handleRun} className="w-full">
              {isRunning ? 'Running…' : 'Run Experiment'}
            </Button>
          </Card>
        </div>

        {/* Results panel */}
        <div className="lg:col-span-2 space-y-4">
          {!exp.experimentId && !isDone && (
            <Card className="flex flex-col items-center justify-center py-16 gap-4">
              <FlaskConical size={40} className="text-text-muted" />
              <p className="text-text-muted text-sm">Configure and run an experiment to see results</p>
            </Card>
          )}

          {isRunning && (
            <Card glow>
              <div className="flex items-center gap-4 py-6 justify-center">
                <Spinner size={28} color="#00FF87" />
                <div>
                  <p className="font-semibold text-text-primary">Experiment running…</p>
                  <p className="text-xs text-text-muted mt-0.5 font-mono">{exp.experimentId}</p>
                </div>
              </div>
            </Card>
          )}

          {isDone && results && (
            <>
              {/* Winner banner */}
              {winner && (
                <Card className="border-data-green/30 bg-data-green/5">
                  <div className="flex items-center gap-4">
                    <Trophy size={28} className="text-data-green" />
                    <div>
                      <p className="text-sm text-text-muted">Best overall strategy</p>
                      <p className="font-display text-xl font-bold text-data-green">
                        {STRATEGY_LABELS[winner] ?? winner}
                      </p>
                    </div>
                  </div>
                </Card>
              )}

              {/* Radar chart */}
              <Card>
                <Card.Header>
                  <Card.Title>Multi-Dimension Comparison</Card.Title>
                  <Card.Subtitle>Normalised quality & efficiency axes</Card.Subtitle>
                </Card.Header>
                <StrategyRadarChart strategies={results} />
              </Card>

              {/* Bitrate chart */}
              <Card>
                <Card.Header>
                  <Card.Title>Average Bitrate</Card.Title>
                  <Card.Subtitle>Lower is better (at same quality)</Card.Subtitle>
                </Card.Header>
                <BitrateBarChart data={bitrateData} />
              </Card>

              {/* Per-strategy table */}
              <Card>
                <Card.Header><Card.Title>Per-Strategy Metrics</Card.Title></Card.Header>
                <div className="overflow-x-auto">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Strategy</th>
                        <th>SSIM</th>
                        <th>Face SSIM</th>
                        <th>SPQI</th>
                        <th>Bitrate (Mbps)</th>
                        <th>Bitrate Save</th>
                        <th>SEES</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(results).map(([key, m]) => (
                        <tr key={key}>
                          <td className="font-medium" style={{ color: STRATEGIES.find((s) => s.id === key)?.color?.replace('text-', '') }}>
                            {STRATEGY_LABELS[key] ?? key}
                            {key === winner && <span className="ml-2 text-data-green text-xs">🏆</span>}
                          </td>
                          <td className="font-mono">{m.avg_ssim?.toFixed(3) ?? '—'}</td>
                          <td className="font-mono">{m.face_ssim?.toFixed(3) ?? '—'}</td>
                          <td className="font-mono">{m.avg_spqi?.toFixed(2) ?? '—'}</td>
                          <td className="font-mono">{m.avg_bitrate_mbps?.toFixed(2) ?? '—'}</td>
                          <td className="font-mono">{m.bitrate_reduction_pct != null ? `${m.bitrate_reduction_pct.toFixed(1)}%` : '—'}</td>
                          <td className="font-mono">{m.sees_score?.toFixed(3) ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
