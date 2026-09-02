/**
 * components/charts/MetricsLineChart.jsx
 * Dual-line Recharts chart: PSNR and SSIM over frames.
 */

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card p-3 text-xs space-y-1" style={{ minWidth: 140 }}>
      <p className="text-text-muted font-mono">Frame {label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex justify-between gap-4">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span className="font-mono text-text-primary font-medium">
            {typeof entry.value === 'number' ? entry.value.toFixed(3) : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function MetricsLineChart({ data = [], className = '' }) {
  // data: [{ frame: 0, psnr: 38.2, ssim: 0.94 }, ...]
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
          {/* Left Y axis — PSNR (dB) */}
          <YAxis
            yAxisId="psnr"
            orientation="left"
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            domain={['auto', 'auto']}
            label={{ value: 'PSNR (dB)', angle: -90, position: 'insideLeft', offset: 20, fill: '#60A5FA', fontSize: 10 }}
          />
          {/* Right Y axis — SSIM (0–1) */}
          <YAxis
            yAxisId="ssim"
            orientation="right"
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            domain={[0, 1]}
            label={{ value: 'SSIM', angle: 90, position: 'insideRight', offset: 16, fill: '#00FF87', fontSize: 10 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          />
          <Line
            yAxisId="psnr"
            type="monotone"
            dataKey="psnr"
            name="PSNR"
            stroke="#60A5FA"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
          <Line
            yAxisId="ssim"
            type="monotone"
            dataKey="ssim"
            name="SSIM"
            stroke="#00FF87"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
