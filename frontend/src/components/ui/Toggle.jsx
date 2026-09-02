/**
 * components/ui/Toggle.jsx
 * Boolean toggle switch. Matches the design system accent color.
 * Used in SettingsPage for feature flags (SEES, bbox display, etc.)
 */


export default function Toggle({
  checked = false,
  onChange,
  label,
  description,
  disabled = false,
  className = '',
  id,
}) {
  const inputId = id ?? `toggle-${label?.replace(/\s+/g, '-').toLowerCase()}`

  return (
    <div className={`flex items-center justify-between ${className}`}>
      {/* Text */}
      {(label || description) && (
        <div className="flex-1 mr-4">
          {label && (
            <label
              htmlFor={inputId}
              className="text-sm font-medium text-text-primary cursor-pointer select-none"
            >
              {label}
            </label>
          )}
          {description && (
            <p className="text-xs text-text-muted mt-0.5">{description}</p>
          )}
        </div>
      )}

      {/* Switch */}
      <label
        htmlFor={inputId}
        className={`relative inline-block w-11 h-6 cursor-pointer ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
      >
        <input
          id={inputId}
          type="checkbox"
          className="sr-only peer"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange?.(e.target.checked)}
        />
        {/* Track */}
        <div
          className={`
            w-11 h-6 rounded-full transition-colors duration-200
            peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent/50
            ${checked ? 'bg-accent' : 'bg-bg-card border border-border-subtle'}
          `}
          style={checked ? { boxShadow: '0 0 10px rgba(79,70,229,0.35)' } : {}}
        />
        {/* Thumb */}
        <div
          className={`
            absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-md
            transition-transform duration-200
            ${checked ? 'translate-x-5' : 'translate-x-0'}
          `}
        />
      </label>
    </div>
  )
}
