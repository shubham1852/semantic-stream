/**
 * components/video/PriorityLegend.jsx
 * Displays the P1–P5 semantic priority tier legend with colors, labels,
 * QP values, and pixel allocation percentages (optional).
 */

import { TierBadge } from '../ui/Badge'

const TIER_DATA = [
  { tier: 'P1', label: 'Face / Person',  color: '#00FF87', qp: 18, desc: 'Highest visual attention' },
  { tier: 'P2', label: 'Text Overlay',   color: '#4ADE80', qp: 22, desc: 'Readable content' },
  { tier: 'P3', label: 'Motion Region',  color: '#F59E0B', qp: 26, desc: 'Optical flow > 2px' },
  { tier: 'P4', label: 'Detected Object',color: '#818CF8', qp: 32, desc: 'Other YOLO objects' },
  { tier: 'P5', label: 'Background',     color: '#EF4444', qp: 40, desc: 'Low attention area' },
]

/**
 * @param {{ allocations?: Record<string, number>, compact?: boolean }} props
 * allocations: optional { P1: 12.4, P2: 3.1, P3: 18.2, P4: 8.9, P5: 57.4 }
 */
export default function PriorityLegend({ allocations = null, compact = false, className = '' }) {
  return (
    <div className={`${className}`}>
      {compact ? (
        /* Compact horizontal row */
        <div className="flex flex-wrap gap-2">
          {TIER_DATA.map(({ tier, label, color }) => (
            <div key={tier} className="flex items-center gap-1.5 text-xs text-text-muted">
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ background: color, boxShadow: `0 0 4px ${color}80` }}
              />
              <span style={{ color }}>{tier}</span>
              <span className="text-text-muted">·</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      ) : (
        /* Full table layout */
        <div className="space-y-2">
          {TIER_DATA.map(({ tier, label, color, qp, desc }) => (
            <div
              key={tier}
              className="flex items-center gap-3 p-2.5 rounded-btn"
              style={{ background: `${color}0D`, border: `1px solid ${color}25` }}
            >
              {/* Color swatch */}
              <div
                className="w-3 h-8 rounded-sm shrink-0"
                style={{ background: color, boxShadow: `0 0 6px ${color}60` }}
              />
              {/* Tier + label */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <TierBadge tier={tier} />
                  <span className="text-sm font-medium text-text-primary">{label}</span>
                </div>
                <p className="text-xs text-text-muted mt-0.5">{desc}</p>
              </div>
              {/* QP value */}
              <div className="text-right shrink-0">
                <div className="font-mono text-sm font-semibold" style={{ color }}>
                  QP {qp}
                </div>
                {allocations && allocations[tier] != null && (
                  <div className="text-xs text-text-muted font-mono">
                    {allocations[tier].toFixed(1)}%
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
