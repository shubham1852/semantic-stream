/**
 * pages/BandwidthPage.jsx
 * Bandwidth profile selector + area chart + simulation trigger.
 * Lets the user pick one of the 5 pre-defined network profiles
 * and run a fresh encode on the last uploaded video under that profile.
 */

import { useState, useEffect } from 'react'
import { Wifi, WifiOff, Zap, TrendingDown, Activity, Play } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import BandwidthChart from '../components/charts/BandwidthChart'
import { getBandwidthProfiles } from '../api/bandwidth'
import { startAnalysis } from '../api/analysis'
import useAppStore from '../store/useAppStore'

/* ─── Static profile metadata ─────────────────────────────── */
const PROFILE_META = {
  strong_wifi: {
    label: 'Strong WiFi',
    icon: Wifi,
    color: '#00FF87',
    desc: '8 Mbps constant with ±0.3 Mbps noise',
    tag: 'Stable',
  },
  weak_wifi: {
    label: 'Weak WiFi',
    icon: Wifi,
    color: '#4ADE80',
    desc: '2 Mbps mean with ±0.6 Mbps jitter and occasional drops',
    tag: 'Jittery',
  },
  '4g_degrading': {
    label: '4G Degrading',
    icon: Activity,
    color: '#F59E0B',
    desc: 'Starts at 5 Mbps, linearly falls to 1.5 Mbps, recovers to 3.5 Mbps',
    tag: 'Degrading',
  },
  burst_loss: {
    label: 'Burst Loss',
    icon: TrendingDown,
    color: '#818CF8',
    desc: '6 Mbps baseline with sudden drops to 0.3 Mbps at t=20s, 50s, 90s',
    tag: 'Bursty',
  },
  stress_test: {
    label: 'Stress Test',
    icon: WifiOff,
    color: '#EF4444',
    desc: 'Alternates between 4 Mbps and 0.5 Mbps every 8 seconds',
    tag: 'Extreme',
  },
}

/* ─── Profile selector card ──────────────────────────────── */
function ProfileCard({ id, meta, selected, onSelect }) {
  const Icon = meta.icon
  return (
    <button
      onClick={() => onSelect(id)}
      className="w-full text-left glass-card rounded-card p-4 transition-all duration-200"
      style={{
        borderColor: selected ? `${meta.color}60` : undefined,
        boxShadow: selected ? `0 0 16px ${meta.color}25` : undefined,
      }}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-9 h-9 rounded-btn flex items-center justify-center shrink-0"
          style={{ background: `${meta.color}18`, border: `1px solid ${meta.color}35` }}
        >
          <Icon size={18} style={{ color: meta.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-0.5">
            <span className="font-display font-semibold text-sm text-text-primary">
              {meta.label}
            </span>
            <span
              className="text-xs font-mono px-1.5 py-0.5 rounded-badge"
              style={{ background: `${meta.color}15`, color: meta.color, border: `1px solid ${meta.color}25` }}
            >
              {meta.tag}
            </span>
          </div>
          <p className="text-xs text-text-muted leading-snug">{meta.desc}</p>
        </div>
      </div>
      {selected && (
        <div className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: meta.color }}>
          <div className="w-1.5 h-1.5 rounded-full bg-current" />
          Active
        </div>
      )}
    </button>
  )
}

/* ─── Main ─────────────────────────────────────────────────── */
export default function BandwidthPage() {
  const [profiles, setProfiles] = useState([])
  const [selected, setSelected] = useState('strong_wifi')
  const [profileData, setProfileData] = useState({})
  const [running, setRunning] = useState(false)
  const [jobId, setJobId] = useState(null)

  const videoId = useAppStore((s) => s.upload.videoId)
  const addToast = useAppStore((s) => s.addToast)

  /* Fetch available profiles */
  useEffect(() => {
    getBandwidthProfiles()
      .then((data) => {
        const list = data?.profiles ?? Object.keys(PROFILE_META)
        setProfiles(list)
        // Build mock chart data for each profile (visual demo)
        const mockData = {}
        list.forEach((p) => { mockData[p] = generateProfileData(p) })
        setProfileData(mockData)
      })
      .catch(() => {
        // Use static keys as fallback
        const list = Object.keys(PROFILE_META)
        setProfiles(list)
        const mockData = {}
        list.forEach((p) => { mockData[p] = generateProfileData(p) })
        setProfileData(mockData)
      })
  }, [])

  const handleRunSimulation = async () => {
    if (!videoId) {
      addToast({ type: 'warning', title: 'No video', message: 'Upload a video first' })
      return
    }
    setRunning(true)
    try {
      const result = await startAnalysis(videoId, { bandwidthProfile: selected })
      setJobId(result.job_id)
      addToast({ type: 'success', title: 'Simulation started', message: `Job: ${result.job_id}` })
    } catch (e) {
      addToast({ type: 'error', title: 'Failed to start', message: e.message })
    } finally {
      setRunning(false)
    }
  }

  const meta = PROFILE_META[selected] ?? {}
  const chartData = profileData[selected] ?? []

  return (
    <PageShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-text-primary">
              Bandwidth Profiles
            </h1>
            <p className="text-sm text-text-muted mt-1">
              Select a network profile and run a simulation to see SemanticStream adapt
            </p>
          </div>
          <Button
            onClick={handleRunSimulation}
            loading={running}
            disabled={!videoId}
            icon={<Play size={16} />}
          >
            Run Simulation
          </Button>
        </div>

        {!videoId && (
          <div className="glass-card rounded-card p-4 flex items-center gap-3 border-data-amber/30">
            <Zap size={16} className="text-data-amber shrink-0" />
            <p className="text-sm text-text-muted">
              No video uploaded yet.{' '}
              <a href="/upload" className="text-accent-light hover:underline">Upload one</a>{' '}
              to run a bandwidth simulation.
            </p>
          </div>
        )}

        {jobId && (
          <div className="glass-card rounded-card p-4 flex items-center gap-3"
            style={{ borderColor: 'rgba(0,255,135,0.3)' }}>
            <div className="live-dot" />
            <p className="text-sm text-data-green font-mono">
              Simulation running — Job ID: {jobId}
            </p>
            <a href={`/results/${jobId}`} className="ml-auto text-xs text-accent-light hover:underline">
              View Results →
            </a>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Profile selector */}
          <div className="space-y-3">
            <h2 className="font-display font-semibold text-text-primary text-sm">
              Select Profile
            </h2>
            {Object.entries(PROFILE_META).map(([id, m]) => (
              <ProfileCard
                key={id}
                id={id}
                meta={m}
                selected={selected === id}
                onSelect={setSelected}
              />
            ))}
          </div>

          {/* Chart + info */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="p-5">
              <div className="flex items-center justify-between mb-4">
                <Card.Title className="flex items-center gap-2">
                  {meta.icon && <meta.icon size={16} style={{ color: meta.color }} />}
                  {meta.label ?? selected}
                </Card.Title>
                <span
                  className="text-xs font-mono px-2 py-0.5 rounded-badge"
                  style={{ background: `${meta.color}15`, color: meta.color, border: `1px solid ${meta.color}25` }}
                >
                  {meta.tag}
                </span>
              </div>
              <p className="text-sm text-text-muted mb-5">{meta.desc}</p>
              <BandwidthChart data={chartData} color={meta.color} />
            </Card>

            {/* Profile stats */}
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: 'Peak Bandwidth', value: chartData.length ? `${Math.max(...chartData.map(d => d.bandwidth)).toFixed(1)} Mbps` : '—' },
                { label: 'Min Bandwidth',  value: chartData.length ? `${Math.min(...chartData.map(d => d.bandwidth)).toFixed(1)} Mbps` : '—' },
                { label: 'Avg Bandwidth',  value: chartData.length ? `${(chartData.reduce((a, d) => a + d.bandwidth, 0) / chartData.length).toFixed(1)} Mbps` : '—' },
              ].map(({ label, value }) => (
                <Card key={label} className="p-4 text-center">
                  <div className="text-lg font-display font-bold text-text-primary font-mono" style={{ color: meta.color }}>
                    {value}
                  </div>
                  <div className="text-xs text-text-muted mt-1">{label}</div>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </div>
    </PageShell>
  )
}

/* ─── Mock profile time-series generator ─────────────────── */
function generateProfileData(profileId) {
  const pts = []
  for (let t = 0; t <= 120; t += 2) {
    let bw
    switch (profileId) {
      case 'strong_wifi':
        bw = 8 + (Math.random() - 0.5) * 0.6
        break
      case 'weak_wifi':
        bw = 2 + (Math.random() - 0.5) * 1.2
        if (Math.random() < 0.05) bw = 0.5
        break
      case '4g_degrading':
        bw = t <= 60
          ? 5 - (3.5 / 60) * t + (Math.random() - 0.5) * 0.4
          : 1.5 + (2 / 60) * (t - 60) + (Math.random() - 0.5) * 0.4
        break
      case 'burst_loss':
        bw = 6
        if ((t >= 20 && t <= 23) || (t >= 50 && t <= 53) || (t >= 90 && t <= 93)) bw = 0.3
        bw += (Math.random() - 0.5) * 0.3
        break
      case 'stress_test':
        bw = Math.floor(t / 8) % 2 === 0 ? 4 : 0.5
        bw += (Math.random() - 0.5) * 0.2
        break
      default:
        bw = 4
    }
    pts.push({ time: t, bandwidth: Math.max(0.1, bw) })
  }
  return pts
}
