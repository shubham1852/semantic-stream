/**
 * components/charts/ConfidenceChart.jsx
 * Line chart showing YOLO detection confidence per frame.
 * Also shows graceful degradation events (dips below 0.5 threshold).
 */

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const val = payload[0]?.value
  const isDegraded = val != null && val < 0.5
  return (
    <div className="glass-card p-3 text-xs space-y-1" style={{ minWidth: 140 }}>
      <p className="text-text-muted font-mono">Frame {label}</p>
      <div className="flex justify-between gap-4">
        <span className="text-text-muted">Confidence</span>
        <span
          className="font-mono font-medium"
          style={{ color: isDegraded ? '#EF4444' : '#60A5FA' }}
        >
          {val != null ? (val * 100).toFixed(1) : '—'}%
        </span>
      </div>
      {isDegraded && (
        <p className="text-data-amber text-xs mt-1">⚠ Graceful degradation active</p>
      )}
    </div>
  )
}

/**
 * @param {{ data: Array<{ frame: number, confidence: number }> }} props
 */
export default function ConfidenceChart({ data = [], className = '' }) {
  return (
    <div className={`w-full h-44 ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="confGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#60A5FA" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#60A5FA" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="confGradientLow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#EF4444" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="frame"
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            domain={[0, 1]}
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          />
          {/* Degradation threshold */}
          <ReferenceLine
            y={0.5}
            stroke="rgba(239,68,68,0.5)"
            strokeDasharray="4 4"
            label={{ value: 'Degradation threshold', position: 'insideTopRight', fill: '#EF4444', fontSize: 10 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="confidence"
            name="Confidence"
            stroke="#60A5FA"
            strokeWidth={2}
            fill="url(#confGradient)"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0, fill: '#60A5FA' }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
