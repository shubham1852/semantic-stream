/**
 * components/ui/Slider.jsx
 * Styled range slider for numeric config values (QP, bandwidth, alpha, etc.)
 * Wraps a native <input type="range"> with the design system's indigo accent.
 */


export default function Slider({
  label,
  value,
  min = 0,
  max = 100,
  step = 1,
  onChange,
  unit = '',
  hint = '',
  disabled = false,
  className = '',
}) {
  const pct = max === min ? 0 : ((value - min) / (max - min)) * 100

  return (
    <div className={`w-full ${className}`}>
      {/* Label row */}
      {label && (
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-text-primary">
            {label}
            {hint && (
              <span className="ml-2 text-xs text-text-muted font-normal">{hint}</span>
            )}
          </label>
          <span className="font-mono text-sm text-accent-light tabular-nums">
            {typeof value === 'number' && step < 1 ? value.toFixed(2) : value}
            {unit}
          </span>
        </div>
      )}

      {/* Track + thumb */}
      <div className="relative flex items-center h-5">
        {/* Filled track */}
        <div
          className="absolute left-0 h-1.5 rounded-full pointer-events-none"
          style={{
            width: `${pct}%`,
            background: 'linear-gradient(90deg, #4F46E5, #818CF8)',
            boxShadow: '0 0 6px rgba(79,70,229,0.4)',
          }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange?.(Number(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            background: `linear-gradient(to right,
              rgba(79,70,229,0.6) 0%, rgba(79,70,229,0.6) ${pct}%,
              rgba(79,70,229,0.12) ${pct}%, rgba(79,70,229,0.12) 100%)`,
          }}
        />
      </div>

      {/* Min/max labels */}
      <div className="flex justify-between mt-1">
        <span className="text-xs text-text-muted font-mono">{min}{unit}</span>
        <span className="text-xs text-text-muted font-mono">{max}{unit}</span>
      </div>
    </div>
  )
}
