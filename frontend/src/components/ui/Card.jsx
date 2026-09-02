/**
 * components/ui/Card.jsx
 * Glassmorphism card with optional header, glow variant, and padding.
 */


export default function Card({
  children,
  className = '',
  glow = false,
  padding = true,
  as: Tag = 'div',
  ...props
}) {
  return (
    <Tag
      className={`
        glass-card
        ${padding ? 'p-6' : ''}
        ${glow ? 'animate-glow-pulse border-accent/40' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </Tag>
  )
}

Card.Header = function CardHeader({ children, className = '' }) {
  return (
    <div className={`mb-4 flex items-center justify-between ${className}`}>
      {children}
    </div>
  )
}

Card.Title = function CardTitle({ children, className = '' }) {
  return (
    <h3 className={`font-display text-base font-semibold text-text-primary ${className}`}>
      {children}
    </h3>
  )
}

Card.Subtitle = function CardSubtitle({ children, className = '' }) {
  return (
    <p className={`text-xs text-text-muted mt-0.5 ${className}`}>{children}</p>
  )
}
