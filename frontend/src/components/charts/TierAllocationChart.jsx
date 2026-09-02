/**
 * components/charts/TierAllocationChart.jsx
 * Stacked bar chart showing QP tier allocations across sampled frames.
 * Each bar = one frame; segments = proportion of pixels in each tier (P1–P5).
 */

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'

const TIER_COLORS = {
  p1: '#00FF87',
  p2: '#4ADE80',
  p3: '#F59E0B',
  p4: '#818CF8',
  p5: '#EF4444',
}

const TIER_LABELS = {
  p1: 'P1 · Face',
  p2: 'P2 · Text',
  p3: 'P3 · Motion',
  p4: 'P4 · Objects',
  p5: 'P5 · Background',
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card p-3 text-xs space-y-1.5" style={{ minWidth: 170 }}>
      <p className="text-text-muted font-mono mb-1">Frame {label}</p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="flex justify-between gap-4">
          <span style={{ color: entry.fill }}>{TIER_LABELS[entry.dataKey] ?? entry.dataKey}</span>
          <span className="font-mono text-text-primary">
            {typeof entry.value === 'number' ? entry.value.toFixed(1) : 0}%
          </span>
        </div>
      ))}
    </div>
  )
}

/**
 * @param {{ data: Array<{frame: number, p1: number, p2: number, p3: number, p4: number, p5: number}> }} props
 * Values are percentages (0–100) summing to 100 per frame.
 */
export default function TierAllocationChart({ data = [], className = '' }) {
  return (
    <div className={`w-full h-56 ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }} barSize={Math.max(4, Math.min(20, 300 / (data.length || 1)))}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="frame"
            tick={{ fill: '#8892A4', fontSize: 10, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#8892A4', fontSize: 11, fontFamily: 'JetBrains Mono' }}
            tickLine={false}
            axisLine={false}
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(79,70,229,0.06)' }} />
          <Legend
            iconType="square"
            iconSize={8}
            formatter={(value) => TIER_LABELS[value] ?? value}
            wrapperStyle={{ fontSize: 11 }}
          />
          {['p5', 'p4', 'p3', 'p2', 'p1'].map((tier) => (
            <Bar
              key={tier}
              dataKey={tier}
              stackId="tiers"
              fill={TIER_COLORS[tier]}
              fillOpacity={0.85}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
