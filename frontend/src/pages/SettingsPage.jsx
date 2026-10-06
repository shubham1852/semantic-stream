/**
 * pages/SettingsPage.jsx
 * All user-configurable settings — reads/writes Zustand settings slice.
 * Sections: Detection Config, QP Override Table, Bandwidth, Display Preferences.
 * NOTE: No <PageShell> wrapper — App.jsx supplies it as a layout route.
 */

import { Settings, Sliders, ToggleLeft, Wifi, RotateCcw, Save } from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Slider from '../components/ui/Slider'
import Toggle from '../components/ui/Toggle'
import useAppStore from '../store/useAppStore'

const TIER_COLORS = {
  P1: '#00FF87', P2: '#4ADE80', P3: '#F59E0B', P4: '#818CF8', P5: '#EF4444',
}
const TIER_LABELS = {
  P1: 'Face / Person', P2: 'High Priority', P3: 'Motion Region', P4: 'Detected Object', P5: 'Background',
}

const BW_PROFILES = [
  { id: 'broadband',     label: 'Broadband (8 Mbps)' },
  { id: 'strong_wifi',  label: 'Strong WiFi (8 Mbps)' },
  { id: 'weak_wifi',    label: 'Weak WiFi (2 Mbps)' },
  { id: '4g_degrading', label: '4G Degrading (5→1.5 Mbps)' },
  { id: 'burst_loss',   label: 'Burst Loss (6 Mbps w/ drops)' },
  { id: 'stress_test',  label: 'Stress Test (4↔0.5 Mbps)' },
]

function SectionHeader({ icon: Icon, title, subtitle, iconColor = '#818CF8' }) {
  return (
    <div className="flex items-start gap-3 mb-5">
      <div
        className="w-8 h-8 rounded-btn flex items-center justify-center shrink-0"
        style={{ background: `${iconColor}18`, border: `1px solid ${iconColor}30` }}
      >
        <Icon size={16} style={{ color: iconColor }} />
      </div>
      <div>
        <h2 className="font-display font-semibold text-text-primary">{title}</h2>
        {subtitle && <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const settings     = useAppStore((s) => s.settings)
  const update       = useAppStore((s) => s.updateSettings)
  const updateQp     = useAppStore((s) => s.updateQp)
  const resetSettings = useAppStore((s) => s.resetSettings)
  const addToast     = useAppStore((s) => s.addToast)

  const handleSave = () => {
    addToast({ type: 'success', title: 'Settings saved', message: 'Preferences persisted to local storage' })
  }

  const handleReset = () => {
    resetSettings()
    addToast({ type: 'info', title: 'Settings reset', message: 'All values restored to defaults' })
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-text-primary">Settings</h1>
          <p className="text-sm text-text-muted mt-1">
            Configure detection parameters, QP tiers, bandwidth defaults and display preferences
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" icon={<RotateCcw size={14} />} onClick={handleReset}>
            Reset
          </Button>
          <Button size="sm" icon={<Save size={14} />} onClick={handleSave}>
            Save
          </Button>
        </div>
      </div>

      {/* ── Detection Configuration ────────────────────────── */}
      <Card className="p-6">
        <SectionHeader
          icon={Settings}
          title="Detection Configuration"
          subtitle="Controls the YOLO detection pipeline and frame sampling behaviour."
          iconColor="#818CF8"
        />
        <div className="space-y-6">
          <Slider
            label="Confidence Threshold"
            hint="Detections below this score are discarded (0.35 = permissive, 0.70 = strict)"
            value={settings.confidenceThreshold}
            min={0.35} max={0.70} step={0.05}
            onChange={(v) => update({ confidenceThreshold: v })}
          />
          <Slider
            label="Frame Sample Rate"
            hint="Run full YOLO inference every N frames (1 = every frame, 10 = every 10th)"
            value={settings.frameSampleRate}
            min={1} max={10} step={1}
            unit=" frames"
            onChange={(v) => update({ frameSampleRate: v })}
          />

          {/* Inference size selector */}
          <div className="space-y-1.5">
            <div className="flex items-baseline justify-between">
              <label className="text-sm font-medium text-text-primary">Inference Size</label>
              <span className="text-xs text-text-muted">Input resolution fed to YOLOv8</span>
            </div>
            <div className="flex gap-3">
              {[416, 640].map((sz) => (
                <button
                  key={sz}
                  onClick={() => update({ inferenceSize: sz })}
                  className="flex-1 py-2.5 rounded-btn text-sm font-mono font-semibold transition-all duration-150"
                  style={{
                    background: settings.inferenceSize === sz
                      ? 'rgba(79,70,229,0.25)'
                      : 'rgba(255,255,255,0.04)',
                    border: settings.inferenceSize === sz
                      ? '1px solid rgba(79,70,229,0.55)'
                      : '1px solid rgba(255,255,255,0.08)',
                    color: settings.inferenceSize === sz ? '#818CF8' : '#8892A4',
                    boxShadow: settings.inferenceSize === sz ? '0 0 12px rgba(79,70,229,0.2)' : undefined,
                  }}
                >
                  {sz}px
                  {sz === 640 && (
                    <span className="ml-1.5 text-xs font-normal opacity-60">(recommended)</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* ── QP Override Table ──────────────────────────────── */}
      <Card className="p-6">
        <SectionHeader
          icon={Sliders}
          title="QP Tier Override"
          subtitle="Quantization parameter per semantic tier. Lower QP = higher quality (more bits). Range: 0–51."
          iconColor="#F59E0B"
        />
        <div className="space-y-5">
          {Object.entries(settings.qp).map(([tier, qp]) => (
            <div key={tier} className="flex items-center gap-4">
              <div
                className="w-28 text-right shrink-0 text-xs font-mono font-semibold leading-tight"
                style={{ color: TIER_COLORS[tier] }}
              >
                <div>{tier}</div>
                <div className="opacity-70 font-normal">{TIER_LABELS[tier]?.split(' ')[0]}</div>
              </div>
              <div className="flex-1">
                <Slider
                  value={qp}
                  min={0} max={51} step={1}
                  onChange={(v) => updateQp(tier, v)}
                  unit=""
                />
              </div>
              {/* Editable number input */}
              <input
                type="number"
                min={0} max={51}
                value={qp}
                onChange={(e) => {
                  const v = Math.max(0, Math.min(51, Number(e.target.value)))
                  if (!isNaN(v)) updateQp(tier, v)
                }}
                className="w-12 text-center font-mono text-sm font-bold rounded-btn outline-none"
                style={{
                  background: `${TIER_COLORS[tier]}12`,
                  border: `1px solid ${TIER_COLORS[tier]}35`,
                  color: TIER_COLORS[tier],
                }}
              />
            </div>
          ))}
        </div>
        <div
          className="mt-4 p-3 rounded-btn"
          style={{ background: 'rgba(79,70,229,0.06)', border: '1px solid rgba(79,70,229,0.15)' }}
        >
          <p className="text-xs text-text-muted">
            QP spread:{' '}
            <span className="text-accent-light font-mono">{settings.qp.P5 - settings.qp.P1}</span>{' '}
            QP units between P1 and P5 · Larger spread = more aggressive background compression
          </p>
        </div>
      </Card>

      {/* ── Bandwidth Default Profile ──────────────────────── */}
      <Card className="p-6">
        <SectionHeader
          icon={Wifi}
          title="Default Bandwidth Profile"
          subtitle="Pre-selected profile when launching a new analysis session."
          iconColor="#60A5FA"
        />
        <select
          value={settings.defaultBandwidthProfile}
          onChange={(e) => update({ defaultBandwidthProfile: e.target.value })}
          className="w-full rounded-btn px-3 py-2.5 text-sm text-text-primary outline-none cursor-pointer"
          style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          {BW_PROFILES.map(({ id, label }) => (
            <option key={id} value={id} style={{ background: '#0F1426' }}>
              {label}
            </option>
          ))}
        </select>
      </Card>

      {/* ── Display Preferences ────────────────────────────── */}
      <Card className="p-6">
        <SectionHeader
          icon={ToggleLeft}
          title="Display Preferences"
          subtitle="Controls what is overlaid on the live camera and heatmap views."
          iconColor="#00FF87"
        />
        <div className="space-y-4">
          <Toggle
            checked={settings.showBoundingBoxes}
            onChange={(v) => update({ showBoundingBoxes: v })}
            label="Show Bounding Boxes"
            description="Overlay YOLO detection boxes on the annotated and heatmap views"
          />
          <Toggle
            checked={settings.showQpValues}
            onChange={(v) => update({ showQpValues: v })}
            label="Show QP Values on Heatmap"
            description="Display numeric QP values inside each detected region's bounding box"
          />
          <Toggle
            checked={settings.showConfidencePct}
            onChange={(v) => update({ showConfidencePct: v })}
            label="Show Confidence % on Boxes"
            description="Append YOLO detection confidence score to each bounding box label"
          />
          <Toggle
            checked={settings.enableSees}
            onChange={(v) => update({ enableSees: v })}
            label="Enable SEES Computation"
            description="Measure and report Semantic Energy Efficiency Score per session"
          />
          <Toggle
            checked={settings.enableSceneDetection}
            onChange={(v) => update({ enableSceneDetection: v })}
            label="Enable Scene Detection"
            description="Detect scene cuts and classify scene type per encoded segment"
          />
        </div>
      </Card>

      {/* ── Save / Reset row ───────────────────────────────── */}
      <div className="flex items-center justify-end gap-3 pb-4">
        <Button variant="ghost" icon={<RotateCcw size={14} />} onClick={handleReset}>
          Reset to Defaults
        </Button>
        <Button icon={<Save size={16} />} onClick={handleSave}>
          Save Settings
        </Button>
      </div>
    </div>
  )
}
