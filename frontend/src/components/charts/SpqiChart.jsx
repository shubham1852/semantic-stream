/**
 * components/charts/SpqiChart.jsx
 * Dual-line chart comparing SPQI and SSIM over frames.
 * SPQI is the novel SemanticStream metric — weighted by semantic region importance.
 * SSIM is the standard reference metric for comparison.
 */

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card p-3 text-xs space-y-1.5" style={{ minWidth: 160 }}>
      <p className="text-text-muted font-mono">Frame {label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex justify-between gap-4">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span className="font-mono text-text-primary font-medium">
            {typeof entry.value === 'number' ? entry.value.toFixed(4) : '—'}
          </span>
        </div>
      ))}
      {payload.length === 2 && payload[0].value != null && payload[1].value != null && (
        <div className="flex justify-between gap-4 border-t border-border-subtle pt-1.5 mt-1">
          <span className="text-text-muted">SPQI gain</span>
          <span
            className="font-mono font-medium"
            style={{ color: payload[0].value >= payload[1].value ? '#00FF87' : '#EF4444' }}
          >
            {((payload[0].value - payload[1].value) * 100).toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  )
}

/**
 * @param {{ data: Array<{ frame: number, spqi: number, ssim: number }> }} props
 */
export default function SpqiChart({ data = [], className = '' }) {
  return (
    <div className={`w-full h-64 ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="frame"
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            label={{ value: 'Frame', position: 'insideBottom', offset: -2, fill: '#8892A4', fontSize: 11 }}
          />
          <YAxis
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            domain={[0, 1]}
            tickFormatter={(v) => v.toFixed(2)}
          />
          {/* Reference line at 0.75 — the SPQI threshold for P1 reallocation */}
          <ReferenceLine
            y={0.75}
            stroke="rgba(245,158,11,0.4)"
            strokeDasharray="4 4"
            label={{ value: 'P1 threshold', position: 'insideTopRight', fill: '#F59E0B', fontSize: 10 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          />
          <Line
            type="monotone"
            dataKey="spqi"
            name="SPQI"
            stroke="#00FF87"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
          <Line
            type="monotone"
            dataKey="ssim"
            name="SSIM"
            stroke="#818CF8"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
