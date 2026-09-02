/**
 * pages/SettingsPage.jsx
 * All user-configurable settings. Persists to localStorage.
 * Sections: QP Override Table, Thresholds, Feature Toggles, Appearance.
 */

import { useState, useEffect } from 'react'
import { Save, RotateCcw, Settings, Sliders, ToggleLeft, Palette } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Slider from '../components/ui/Slider'
import Toggle from '../components/ui/Toggle'
import useAppStore from '../store/useAppStore'

const STORAGE_KEY = 'semanticstream_settings'

const DEFAULTS = {
  // QP overrides per tier (P1–P5)
  qp: { P1: 18, P2: 22, P3: 26, P4: 32, P5: 40 },
  // Analysis thresholds
  confidenceThreshold: 0.45,
  frameSampleRate: 5,
  temporalAlpha: 0.3,
  bwSimulationSpeed: 1.0,
  // Toggles
  showBoundingBoxes: true,
  showQpValues: true,
  enableSees: true,
  enableSceneDetection: true,
  darkMode: true,
}

const TIER_COLORS = {
  P1: '#00FF87', P2: '#4ADE80', P3: '#F59E0B', P4: '#818CF8', P5: '#EF4444',
}
const TIER_LABELS = {
  P1: 'Face / Person', P2: 'Text Overlay', P3: 'Motion Region', P4: 'Detected Object', P5: 'Background',
}

function SectionHeader({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex items-start gap-3 mb-5">
      <div className="w-8 h-8 rounded-btn flex items-center justify-center shrink-0"
        style={{ background: 'rgba(79,70,229,0.15)', border: '1px solid rgba(79,70,229,0.3)' }}>
        <Icon size={16} className="text-accent-light" />
      </div>
      <div>
        <h2 className="font-display font-semibold text-text-primary">{title}</h2>
        {subtitle && <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const [settings, setSettings] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      return stored ? { ...DEFAULTS, ...JSON.parse(stored) } : DEFAULTS
    } catch {
      return DEFAULTS
    }
  })
  const [saved, setSaved] = useState(false)
  const addToast = useAppStore((s) => s.addToast)

  const set = (key, value) => setSettings((prev) => ({ ...prev, [key]: value }))
  const setQp = (tier, value) => setSettings((prev) => ({
    ...prev,
    qp: { ...prev.qp, [tier]: value },
  }))

  const handleSave = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
      setSaved(true)
      addToast({ type: 'success', title: 'Settings saved', message: 'Preferences persisted to local storage' })
      setTimeout(() => setSaved(false), 2000)
    } catch {
      addToast({ type: 'error', title: 'Save failed', message: 'Could not write to local storage' })
    }
  }

  const handleReset = () => {
    setSettings(DEFAULTS)
    localStorage.removeItem(STORAGE_KEY)
    addToast({ type: 'info', title: 'Settings reset', message: 'All values restored to defaults' })
  }

  return (
    <PageShell>
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-text-primary">Settings</h1>
            <p className="text-sm text-text-muted mt-1">
              Configure encoding parameters, analysis thresholds, and display preferences
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" icon={<RotateCcw size={14} />} onClick={handleReset}>
              Reset
            </Button>
            <Button size="sm" icon={<Save size={14} />} onClick={handleSave}>
              {saved ? 'Saved!' : 'Save'}
            </Button>
          </div>
        </div>

        {/* ── QP Override Table ──────────────────────────── */}
        <Card className="p-6">
          <SectionHeader
            icon={Sliders}
            title="QP Tier Override"
            subtitle="Quantization parameter per semantic tier. Lower QP = higher quality (more bits). Valid range: 0–51."
          />
          <div className="space-y-5">
            {Object.entries(settings.qp).map(([tier, qp]) => (
              <div key={tier} className="flex items-center gap-4">
                {/* Tier badge */}
                <div
                  className="w-24 text-right shrink-0 text-xs font-mono font-semibold"
                  style={{ color: TIER_COLORS[tier] }}
                >
                  {tier} · {TIER_LABELS[tier]?.split(' ')[0]}
                </div>
                <div className="flex-1">
                  <Slider
                    value={qp}
                    min={0}
                    max={51}
                    step={1}
                    onChange={(v) => setQp(tier, v)}
                    unit=""
                  />
                </div>
                <div
                  className="w-10 text-right font-mono text-sm font-bold shrink-0"
                  style={{ color: TIER_COLORS[tier] }}
                >
                  {qp}
                </div>
              </div>
            ))}
          </div>
          {/* Quick compare */}
          <div className="mt-4 p-3 rounded-btn" style={{ background: 'rgba(79,70,229,0.06)', border: '1px solid rgba(79,70,229,0.15)' }}>
            <p className="text-xs text-text-muted">
              QP spread: <span className="text-accent-light font-mono">{settings.qp.P5 - settings.qp.P1}</span> QP units between P1 and P5
              {' · '}
              Larger spread = more aggressive background compression
            </p>
          </div>
        </Card>

        {/* ── Analysis Thresholds ────────────────────────── */}
        <Card className="p-6">
          <SectionHeader
            icon={Settings}
            title="Analysis Parameters"
            subtitle="Controls the detection pipeline and temporal smoothing behaviour."
          />
          <div className="space-y-6">
            <Slider
              label="Confidence Threshold"
              hint="YOLO detections below this are discarded"
              value={settings.confidenceThreshold}
              min={0.1} max={0.9} step={0.05}
              onChange={(v) => set('confidenceThreshold', v)}
            />
            <Slider
              label="Frame Sample Rate"
              hint="Process 1 in every N frames"
              value={settings.frameSampleRate}
              min={1} max={30} step={1}
              unit=" fps"
              onChange={(v) => set('frameSampleRate', v)}
            />
            <Slider
              label="Temporal Smoothing Alpha (α)"
              hint="Blends current/previous priority map. Lower = smoother"
              value={settings.temporalAlpha}
              min={0.05} max={0.95} step={0.05}
              onChange={(v) => set('temporalAlpha', v)}
            />
            <Slider
              label="Bandwidth Simulation Speed"
              hint="Multiplier for the time-series playback rate"
              value={settings.bwSimulationSpeed}
              min={0.25} max={4} step={0.25}
              unit="×"
              onChange={(v) => set('bwSimulationSpeed', v)}
            />
          </div>
        </Card>

        {/* ── Feature Toggles ───────────────────────────── */}
        <Card className="p-6">
          <SectionHeader
            icon={ToggleLeft}
            title="Feature Toggles"
            subtitle="Enable or disable optional processing and display features."
          />
          <div className="space-y-4">
            <Toggle
              checked={settings.showBoundingBoxes}
              onChange={(v) => set('showBoundingBoxes', v)}
              label="Show Bounding Boxes"
              description="Overlay YOLO detection boxes on the heatmap view"
            />
            <Toggle
              checked={settings.showQpValues}
              onChange={(v) => set('showQpValues', v)}
              label="Show QP Values on Heatmap"
              description="Display numeric QP values inside bounding boxes"
            />
            <Toggle
              checked={settings.enableSees}
              onChange={(v) => set('enableSees', v)}
              label="Enable SEES Computation"
              description="Measure and report Semantic Energy Efficiency Score"
            />
            <Toggle
              checked={settings.enableSceneDetection}
              onChange={(v) => set('enableSceneDetection', v)}
              label="Enable Scene Detection"
              description="Detect scene cuts and classify scene type per segment"
            />
          </div>
        </Card>

        {/* ── Appearance ────────────────────────────────── */}
        <Card className="p-6">
          <SectionHeader
            icon={Palette}
            title="Appearance"
            subtitle="UI display preferences."
          />
          <Toggle
            checked={settings.darkMode}
            onChange={(v) => set('darkMode', v)}
            label="Dark Mode"
            description="SemanticStream is designed for dark mode — toggling this may reduce visual quality"
          />
        </Card>

        {/* ── Save row ──────────────────────────────────── */}
        <div className="flex items-center justify-end gap-3 pb-4">
          <Button variant="ghost" icon={<RotateCcw size={14} />} onClick={handleReset}>
            Reset to Defaults
          </Button>
          <Button icon={<Save size={16} />} onClick={handleSave}>
            {saved ? '✓ Saved' : 'Save Settings'}
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
