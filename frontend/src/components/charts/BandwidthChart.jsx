/**
 * components/charts/BandwidthChart.jsx
 * Area chart showing bandwidth profile time series.
 */

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card p-3 text-xs space-y-1">
      <p className="text-text-muted font-mono">t={label}s</p>
      <p className="font-mono font-medium text-data-blue">
        {payload[0].value?.toFixed(1)} Mbps
      </p>
    </div>
  )
}

export default function BandwidthChart({ profile = [], profileName = '', className = '' }) {
  // profile: array of bandwidth values (Mbps) indexed by time
  const chartData = profile.map((bw, i) => ({ t: i, bw }))

  return (
    <div className={`w-full h-44 ${className}`}>
      {profileName && (
        <p className="text-xs text-text-muted mb-2 font-mono">
          Profile: <span className="text-data-blue">{profileName}</span>
        </p>
      )}
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="bwGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#60A5FA" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#60A5FA" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="t"
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}s`}
          />
          <YAxis
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}M`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="bw"
            stroke="#60A5FA"
            strokeWidth={2}
            fill="url(#bwGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
