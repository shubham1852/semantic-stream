/**
 * pages/UploadPage.jsx
 * 4-step flow: upload → config → trigger analysis → redirect to results.
 */

import { Fragment, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings2, Play, ChevronRight } from 'lucide-react'
import { getBandwidthProfiles } from '../api/bandwidth'
import { startAnalysis } from '../api/analysis'
import useAppStore from '../store/useAppStore'
import VideoUploader from '../components/video/VideoUploader'
import ProgressBar from '../components/ui/ProgressBar'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Spinner from '../components/ui/Spinner'
import { useJobPoller } from '../hooks/useJobPoller'

const STEPS = ['Upload Video', 'Configure', 'Analyse', 'Results']

function StepIndicator({ current }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEPS.map((label, i) => (
        <Fragment key={label}>
          <div className="flex items-center gap-2">
            <div
              className={`
                w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300
                ${i < current ? 'bg-data-green text-black'
                  : i === current ? 'bg-accent text-white shadow-glow'
                  : 'bg-bg-card text-text-muted border border-border-subtle'}
              `}
            >
              {i < current ? '✓' : i + 1}
            </div>
            <span className={`text-sm hidden sm:block ${i === current ? 'text-text-primary font-medium' : 'text-text-muted'}`}>
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`flex-1 h-px mx-2 transition-colors duration-300 ${i < current ? 'bg-data-green/40' : 'bg-border-subtle'}`} />
          )}
        </Fragment>
      ))}
    </div>
  )
}

export default function UploadPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [profiles, setProfiles] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const upload = useAppStore((s) => s.upload)
  const analysis = useAppStore((s) => s.analysis)
  const config = analysis.config
  const setAnalysisConfig = useAppStore((s) => s.setAnalysisConfig)
  const setAnalysisQueued = useAppStore((s) => s.setAnalysisQueued)
  const addToast = useAppStore((s) => s.addToast)

  // Fetch bandwidth profiles for dropdown
  useEffect(() => {
    getBandwidthProfiles()
      .then((d) => setProfiles(d?.profiles ?? {}))
      .catch(() => {})
  }, [])

  // Poll when we have a jobId
  const { status: jobStatus, progressPct } = useJobPoller(analysis.jobId)

  // Move to step 3 after upload
  const handleUploadComplete = (_videoId) => {
    setStep(1)
  }

  // Auto-redirect when done
  useEffect(() => {
    if (jobStatus === 'done' || jobStatus === 'complete' || jobStatus === 'completed') {
      setStep(3)
      setTimeout(() => navigate(`/results/${analysis.jobId}`), 1200)
    }
  }, [jobStatus, analysis.jobId, navigate])

  const handleStartAnalysis = async () => {
    if (!upload.videoId) return
    setSubmitting(true)
    try {
      const data = await startAnalysis(upload.videoId, config)
      setAnalysisQueued(data.job_id)
      setStep(2)
      addToast({ type: 'success', title: 'Analysis queued', message: `Job ID: ${data.job_id?.slice(0, 8)}` })
    } catch (err) {
      addToast({ type: 'error', title: 'Failed to start analysis', message: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto animate-slide-up">
      <StepIndicator current={step} />

      {/* Step 0: Upload */}
      {step === 0 && (
        <Card>
          <Card.Header>
            <div>
              <Card.Title>Upload a Video</Card.Title>
              <Card.Subtitle>MP4, MOV, or AVI · Max 2 GB</Card.Subtitle>
            </div>
          </Card.Header>
          <VideoUploader onUploadComplete={handleUploadComplete} />
          {upload.status === 'done' && (
            <div className="mt-4 flex justify-end">
              <Button icon={ChevronRight} onClick={() => setStep(1)}>
                Configure Analysis
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* Step 1: Configure */}
      {step === 1 && (
        <Card>
          <Card.Header>
            <div>
              <Card.Title>Analysis Configuration</Card.Title>
              <Card.Subtitle>Tune detection and compression settings</Card.Subtitle>
            </div>
            <Settings2 size={18} className="text-accent-light" />
          </Card.Header>

          <div className="space-y-5">
            {/* Frame sample rate */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Frame Sample Rate
                <span className="ml-2 text-xs text-text-muted font-normal">Analyse every Nth frame</span>
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range" min="1" max="30" step="1"
                  value={config.frameSampleRate}
                  onChange={(e) => setAnalysisConfig({ frameSampleRate: Number(e.target.value) })}
                  className="flex-1 accent-accent"
                />
                <span className="font-mono text-accent-light w-8 text-right">{config.frameSampleRate}</span>
              </div>
            </div>

            {/* Confidence threshold */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Confidence Threshold
                <span className="ml-2 text-xs text-text-muted font-normal">Min YOLO detection score</span>
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range" min="0.1" max="1.0" step="0.05"
                  value={config.confidenceThreshold}
                  onChange={(e) => setAnalysisConfig({ confidenceThreshold: Number(e.target.value) })}
                  className="flex-1 accent-accent"
                />
                <span className="font-mono text-accent-light w-12 text-right">
                  {config.confidenceThreshold.toFixed(2)}
                </span>
              </div>
            </div>

            {/* Bandwidth profile */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Bandwidth Profile
                <span className="ml-2 text-xs text-text-muted font-normal">Simulation scenario</span>
              </label>
              <select
                className="select-field"
                value={config.bandwidthProfile}
                onChange={(e) => setAnalysisConfig({ bandwidthProfile: e.target.value })}
              >
                <option value="">None (no simulation)</option>
                {Object.keys(profiles).map((p) => (
                  <option key={p} value={p}>{p.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>

            {/* Run comparison */}
            <div className="flex items-center justify-between p-4 rounded-btn" style={{ background: 'rgba(79,70,229,0.06)', border: '1px solid rgba(79,70,229,0.15)' }}>
              <div>
                <p className="text-sm font-medium text-text-primary">Run 3-Strategy Comparison</p>
                <p className="text-xs text-text-muted mt-0.5">
                  Also runs Uniform ABR + Static ROI alongside SemanticStream
                </p>
              </div>
              <label className="relative inline-block w-10 h-6 cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={config.runComparison}
                  onChange={(e) => setAnalysisConfig({ runComparison: e.target.checked })}
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${config.runComparison ? 'bg-accent' : 'bg-bg-card border border-border-subtle'}`} />
                <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${config.runComparison ? 'translate-x-4' : ''}`} />
              </label>
            </div>

            <div className="flex gap-3 pt-2">
              <Button variant="ghost" onClick={() => setStep(0)}>Back</Button>
              <Button icon={Play} loading={submitting} onClick={handleStartAnalysis} className="flex-1">
                Start Analysis
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Step 2: Progress */}
      {step === 2 && (
        <Card glow>
          <Card.Header>
            <Card.Title>Analysis Running</Card.Title>
            <Spinner size={20} />
          </Card.Header>
          <div className="space-y-4">
            <p className="text-sm text-text-muted">
              YOLO is analysing your video frame-by-frame. Hang tight…
            </p>
            <ProgressBar value={progressPct} label={`Job ${analysis.jobId?.slice(0, 8)} · ${jobStatus}`} color="green" />
            <p className="font-mono text-xs text-text-muted">Status: {jobStatus}</p>
          </div>
        </Card>
      )}

      {/* Step 3: Redirect */}
      {step === 3 && (
        <Card>
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="text-5xl">🎉</div>
            <p className="font-display text-xl font-bold text-data-green">Analysis Complete!</p>
            <p className="text-text-muted text-sm">Redirecting to results…</p>
            <Spinner size={24} color="#00FF87" />
          </div>
        </Card>
      )}
    </div>
  )
}
