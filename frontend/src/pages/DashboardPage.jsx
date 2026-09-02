/**
 * pages/DashboardPage.jsx
 * Overview: stat cards, recent history table, quick-start CTAs.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Film, Cpu, TrendingUp, Zap,
  ArrowRight, Upload, Camera, FlaskConical, Clock,
} from 'lucide-react'
import { getHistory } from '../api/videos'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { StatusBadge } from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'

function StatCard({ icon: Icon, label, value, sub, color = 'text-accent-light', glow = false }) {
  return (
    <Card className={`flex flex-col gap-1 ${glow ? 'animate-glow-pulse' : ''}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-text-muted font-medium uppercase tracking-widest">{label}</span>
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: 'rgba(79,70,229,0.12)' }}
        >
          <Icon size={16} className={color} />
        </div>
      </div>
      <p className={`font-display text-3xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-text-muted mt-1">{sub}</p>}
    </Card>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getHistory(5, 0)
      .then((data) => setSessions(data?.sessions ?? []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false))
  }, [])

  const totalVideos = sessions.length
  const avgSsim = sessions.length
    ? (sessions.reduce((s, x) => s + (x.avg_ssim ?? 0), 0) / sessions.length).toFixed(3)
    : '—'

  return (
    <div className="space-y-8 animate-slide-up">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold text-text-primary">
          Welcome to <span className="gradient-text">SemanticStream</span>
        </h2>
        <p className="text-text-muted text-sm mt-1">
          Semantic-aware adaptive video compression using YOLO scene understanding
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Film}     label="Total Sessions" value={totalVideos} sub="analysis runs" color="text-accent-light" />
        <StatCard icon={TrendingUp} label="Avg SSIM"    value={avgSsim}     sub="higher is better (max 1.0)" color="text-data-green" glow />
        <StatCard icon={Cpu}      label="Strategies"    value="3"            sub="Uniform · Static ROI · Semantic" color="text-data-amber" />
        <StatCard icon={Zap}      label="Priority Tiers" value="P1–P5"       sub="Face → Background" color="text-data-blue" />
      </div>

      {/* Quick start CTA */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="group cursor-pointer hover:border-accent/40 transition-all" onClick={() => navigate('/upload')}>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-card flex items-center justify-center bg-accent/10 border border-accent/20 group-hover:bg-accent/20 transition-colors">
              <Upload size={22} className="text-accent-light" />
            </div>
            <div>
              <p className="font-semibold text-text-primary">Upload & Analyse</p>
              <p className="text-xs text-text-muted mt-0.5">Upload a video and run semantic analysis</p>
            </div>
            <ArrowRight size={18} className="text-text-muted ml-auto group-hover:text-accent-light transition-colors" />
          </div>
        </Card>

        <Card className="group cursor-pointer hover:border-data-green/40 transition-all" onClick={() => navigate('/experiments')}>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-card flex items-center justify-center bg-data-green/5 border border-data-green/20 group-hover:bg-data-green/10 transition-colors">
              <FlaskConical size={22} className="text-data-green" />
            </div>
            <div>
              <p className="font-semibold text-text-primary">Run Experiment</p>
              <p className="text-xs text-text-muted mt-0.5">Compare 3 strategies head-to-head</p>
            </div>
            <ArrowRight size={18} className="text-text-muted ml-auto group-hover:text-data-green transition-colors" />
          </div>
        </Card>

        <Card className="group cursor-pointer hover:border-data-blue/40 transition-all" onClick={() => navigate('/live')}>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-card flex items-center justify-center bg-data-blue/5 border border-data-blue/20 group-hover:bg-data-blue/10 transition-colors">
              <Camera size={22} className="text-data-blue" />
            </div>
            <div>
              <p className="font-semibold text-text-primary">Live Camera</p>
              <p className="text-xs text-text-muted mt-0.5">Real-time YOLO detection via WebSocket</p>
            </div>
            <ArrowRight size={18} className="text-text-muted ml-auto group-hover:text-data-blue transition-colors" />
          </div>
        </Card>
      </div>

      {/* Recent sessions table */}
      <Card>
        <Card.Header>
          <div>
            <Card.Title>Recent Sessions</Card.Title>
            <Card.Subtitle>Latest 5 analysis runs</Card.Subtitle>
          </div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/history')}>
            View all
          </Button>
        </Card.Header>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner size={28} />
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <Clock size={32} className="text-text-muted" />
            <p className="text-text-muted text-sm">No sessions yet — upload a video to get started</p>
            <Button size="sm" onClick={() => navigate('/upload')}>Upload Video</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Video</th>
                  <th>Strategy</th>
                  <th>Avg SSIM</th>
                  <th>Status</th>
                  <th>Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id ?? s.job_id} className="cursor-pointer" onClick={() => navigate(`/results/${s.job_id ?? s.id}`)}>
                    <td className="font-mono text-xs text-text-primary truncate max-w-[180px]">
                      {s.filename ?? s.video_id ?? '—'}
                    </td>
                    <td className="text-text-muted">{s.strategy ?? 'semanticstream'}</td>
                    <td className="font-mono text-data-green">{s.avg_ssim?.toFixed(3) ?? '—'}</td>
                    <td><StatusBadge status={s.status ?? 'done'} /></td>
                    <td className="text-text-muted text-xs">
                      {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td>
                      <ArrowRight size={14} className="text-text-muted" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
