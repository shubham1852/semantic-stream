/**
 * components/ui/Badge.jsx
 * Priority tier badges (P1–P5), status badges, and generic colored badges.
 */

const TIER_LABELS = {
  P1: 'Face',
  P2: 'Text',
  P3: 'Motion',
  P4: 'Object',
  P5: 'Background',
}

export function TierBadge({ tier, showLabel = false, className = '' }) {
  const t = String(tier || 'P3').toUpperCase().replace('TIER_', '')
  return (
    <span className={`tier-badge tier-${t.toLowerCase()} ${className}`}>
      {t}
      {showLabel && TIER_LABELS[t] ? ` · ${TIER_LABELS[t]}` : ''}
    </span>
  )
}

const statusConfig = {
  queued:    { color: 'text-data-blue  bg-data-blue/10  border-data-blue/30',  label: 'Queued' },
  running:   { color: 'text-data-amber bg-data-amber/10 border-data-amber/30', label: 'Running' },
  done:      { color: 'text-data-green bg-data-green/10 border-data-green/30', label: 'Done' },
  complete:  { color: 'text-data-green bg-data-green/10 border-data-green/30', label: 'Complete' },
  completed: { color: 'text-data-green bg-data-green/10 border-data-green/30', label: 'Complete' },
  error:     { color: 'text-data-red   bg-data-red/10   border-data-red/30',   label: 'Error' },
  failed:    { color: 'text-data-red   bg-data-red/10   border-data-red/30',   label: 'Failed' },
  idle:      { color: 'text-text-muted bg-white/5       border-white/10',       label: 'Idle' },
}

export function StatusBadge({ status = 'idle', className = '' }) {
  const cfg = statusConfig[status.toLowerCase()] ?? statusConfig.idle
  return (
    <span
      className={`tier-badge border ${cfg.color} ${className}`}
    >
      {status.toLowerCase() === 'running' && (
        <span className="live-dot mr-1.5" />
      )}
      {cfg.label}
    </span>
  )
}

const badgeVariants = {
  green:   'text-data-green bg-data-green/10 border-data-green/30',
  purple:  'text-accent-light bg-accent/20 border-accent-light/30',
  indigo:  'text-accent-light bg-accent/20 border-accent-light/30',
  blue:    'text-data-blue bg-data-blue/10 border-data-blue/30',
  amber:   'text-data-amber bg-data-amber/10 border-data-amber/30',
  red:     'text-data-red bg-data-red/10 border-data-red/30',
  default: 'text-text-muted bg-white/5 border-border-subtle',
}

export function Badge({ children, variant = 'default', tier, showLabel, className = '', ...props }) {
  if (tier) {
    return <TierBadge tier={tier} showLabel={showLabel} className={className} />
  }

  const variantClass = badgeVariants[variant] || badgeVariants.default

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${variantClass} ${className}`}
      {...props}
    >
      {children}
    </span>
  )
}

export default Badge

