/**
 * components/charts/QpHeatmapGrid.jsx
 * D3-inspired CSS grid heatmap showing per-frame QP tier assignments.
 * Uses design system tier colors (P1–P5).
 */

import { useMemo } from 'react'
import Tooltip from '../ui/Tooltip'

const TIER_COLORS = {
  P1: '#00FF87',
  P2: '#4ADE80',
  P3: '#F59E0B',
  P4: '#818CF8',
  P5: '#EF4444',
}

const TIER_LABELS = {
  P1: 'Face',
  P2: 'Text',
  P3: 'Motion',
  P4: 'Object',
  P5: 'Background',
}

const QP_VALUES = { P1: 18, P2: 22, P3: 26, P4: 32, P5: 40 }

/**
 * @param {{ frames: Array<{ frame: number, tier: string, qp: number }> }} props
 */
export default function QpHeatmapGrid({ frames = [], maxDisplay = 120, className = '' }) {
  const displayFrames = useMemo(
    () => frames.slice(0, maxDisplay),
    [frames, maxDisplay]
  )

  if (!displayFrames.length) {
    return (
      <div className={`flex items-center justify-center h-32 text-text-muted text-sm ${className}`}>
        No frame data available
      </div>
    )
  }

  return (
    <div className={className}>
      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-4">
        {Object.entries(TIER_LABELS).map(([tier, label]) => (
          <div key={tier} className="flex items-center gap-1.5 text-xs text-text-muted">
            <span
              className="w-3 h-3 rounded-sm shrink-0"
              style={{ background: TIER_COLORS[tier], opacity: 0.8 }}
            />
            {tier} · {label} (QP {QP_VALUES[tier]})
          </div>
        ))}
      </div>

      {/* Grid */}
      <div
        className="grid gap-0.5"
        style={{
          gridTemplateColumns: 'repeat(auto-fill, minmax(16px, 1fr))',
        }}
      >
        {displayFrames.map((f, i) => {
          const tier = (f.tier ?? 'P3').toUpperCase().replace('TIER_', '')
          const color = TIER_COLORS[tier] ?? '#818CF8'
          return (
            <Tooltip
              key={i}
              content={`Frame ${f.frame ?? i} · ${tier} (${TIER_LABELS[tier] ?? ''}) · QP ${f.qp ?? QP_VALUES[tier] ?? '?'}`}
              position="top"
            >
              <div
                className="w-4 h-4 rounded-sm cursor-default transition-transform hover:scale-125"
                style={{ background: color, opacity: 0.75 }}
              />
            </Tooltip>
          )
        })}
      </div>

      <p className="text-xs text-text-muted mt-3 font-mono">
        Showing {displayFrames.length} of {frames.length} frames
      </p>
    </div>
  )
}
