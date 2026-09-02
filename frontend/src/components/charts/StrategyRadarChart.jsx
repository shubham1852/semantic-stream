/**
 * components/charts/StrategyRadarChart.jsx
 * Radar chart comparing strategies across multiple quality dimensions.
 */

import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer, Legend, Tooltip,
} from 'recharts'

const STRATEGY_COLORS = {
  uniform_abr:    '#EF4444',
  static_roi:     '#F59E0B',
  semanticstream: '#00FF87',
}

const STRATEGY_LABELS = {
  uniform_abr:    'Uniform ABR',
  static_roi:     'Static ROI',
  semanticstream: 'SemanticStream',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card p-3 text-xs space-y-1.5">
      {payload.map((entry) => (
        <div key={entry.name} className="flex justify-between gap-3">
          <span style={{ color: entry.color }}>{STRATEGY_LABELS[entry.name] ?? entry.name}</span>
          <span className="font-mono text-text-primary">{Number(entry.value).toFixed(3)}</span>
        </div>
      ))}
    </div>
  )
}

/**
 * @param {Record<string, { avg_spqi, avg_ssim, avg_bitrate_mbps, face_ssim, bg_ssim, sees_score, bitrate_reduction_pct }>} strategies
 */
export default function StrategyRadarChart({ strategies = {}, className = '' }) {
  const strategyKeys = Object.keys(strategies)

  const dimensions = ['SSIM', 'SPQI', 'Bitrate Save', 'Face SSIM', 'SEES Score']

  const chartData = dimensions.map((dim, i) => {
    const row = { dimension: dim }
    strategyKeys.forEach((key) => {
      const s = strategies[key]
      const rawValues = [
        s.avg_ssim ?? 0,
        (s.avg_spqi ?? 0) / 100,
        (s.bitrate_reduction_pct ?? 0) / 100,
        s.face_ssim ?? 0,
        (s.sees_score ?? 0) / 100,
      ]
      row[key] = parseFloat(rawValues[i].toFixed(4))
    })
    return row
  })

  return (
    <div className={`w-full h-72 ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={chartData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
          <PolarGrid stroke="rgba(79,70,229,0.2)" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'Inter' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 1]}
            tick={{ fill: '#8892A4', fontSize: 9 }}
            tickCount={4}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(value) => STRATEGY_LABELS[value] ?? value}
            wrapperStyle={{ fontSize: 12 }}
          />
          {strategyKeys.map((key) => (
            <Radar
              key={key}
              name={key}
              dataKey={key}
              stroke={STRATEGY_COLORS[key] ?? '#818CF8'}
              fill={STRATEGY_COLORS[key] ?? '#818CF8'}
              fillOpacity={0.12}
              strokeWidth={2}
            />
          ))}
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
