/**
 * components/ui/ProgressBar.jsx
 * Animated gradient progress bar for job tracking.
 */


export default function ProgressBar({
  value = 0,        // 0–100
  showLabel = true,
  label,
  size = 'md',      // sm | md | lg
  color = 'accent', // accent | green | amber
  className = '',
}) {
  const clamped = Math.max(0, Math.min(100, value))

  const heightClass = { sm: 'h-1', md: 'h-2', lg: 'h-3' }[size]

  const gradients = {
    accent: 'from-accent via-accent-light to-data-blue',
    green:  'from-data-green via-emerald-400 to-data-blue',
    amber:  'from-data-amber via-yellow-400 to-data-red',
  }

  return (
    <div className={`w-full ${className}`}>
      {(showLabel || label) && (
        <div className="flex justify-between mb-1.5">
          <span className="text-xs text-text-muted">{label ?? 'Progress'}</span>
          <span className="text-xs font-mono text-accent-light">{clamped}%</span>
        </div>
      )}
      <div
        className={`w-full ${heightClass} rounded-full overflow-hidden`}
        style={{ background: 'rgba(79,70,229,0.12)' }}
      >
        <div
          className={`h-full rounded-full bg-gradient-to-r ${gradients[color]} transition-all duration-500 ease-out`}
          style={{
            width: `${clamped}%`,
            boxShadow: color === 'green'
              ? '0 0 8px rgba(0,255,135,0.5)'
              : '0 0 8px rgba(79,70,229,0.5)',
          }}
        />
      </div>
    </div>
  )
}
