/**
 * components/charts/BitrateBarChart.jsx
 * Bar chart comparing avg bitrate across strategies.
 */

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, LabelList,
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
  const d = payload[0]
  return (
    <div className="glass-card p-3 text-xs space-y-1">
      <p className="text-text-muted">{STRATEGY_LABELS[d.payload.strategy] ?? d.payload.strategy}</p>
      <p className="font-mono font-medium" style={{ color: d.fill }}>
        {d.value?.toFixed(2)} Mbps
      </p>
    </div>
  )
}

export default function BitrateBarChart({ data = [], className = '' }) {
  // data: [{ strategy: 'uniform_abr', bitrate: 4.2 }, ...]
  const chartData = data.map((d) => ({
    ...d,
    label: STRATEGY_LABELS[d.strategy] ?? d.strategy,
  }))

  return (
    <div className={`w-full h-52 ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 16, right: 8, left: -16, bottom: 0 }} barSize={40}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: '#8892A4', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}M`}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(79,70,229,0.08)' }} />
          <Bar dataKey="bitrate" radius={[6, 6, 0, 0]}>
            {chartData.map((entry) => (
              <Cell
                key={entry.strategy}
                fill={STRATEGY_COLORS[entry.strategy] ?? '#818CF8'}
                fillOpacity={0.85}
              />
            ))}
            <LabelList
              dataKey="bitrate"
              position="top"
              formatter={(v) => `${v?.toFixed(1)}M`}
              style={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
