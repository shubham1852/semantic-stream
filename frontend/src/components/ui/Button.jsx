/**
 * components/ui/Button.jsx
 * Primary reusable button with variants, sizes, and loading state.
 */

import Spinner from './Spinner'

const variantClasses = {
  primary: 'bg-accent hover:bg-accent-light text-white shadow-glow hover:shadow-glow focus:ring-accent/30',
  secondary: 'bg-bg-card hover:bg-accent/10 text-text-primary border border-border-subtle',
  ghost: 'bg-transparent hover:bg-accent/10 text-text-muted hover:text-text-primary border border-border-subtle hover:border-accent-light',
  danger: 'bg-data-red/10 hover:bg-data-red/20 text-data-red border border-data-red/30',
  success: 'bg-data-green/10 hover:bg-data-green/20 text-data-green border border-data-green/30',
}

const sizeClasses = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-5 py-2.5 text-sm gap-2',
  lg: 'px-7 py-3 text-base gap-2.5',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon: Icon,
  iconRight,
  className = '',
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center font-semibold rounded-btn
        transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-primary
        disabled:opacity-40 disabled:cursor-not-allowed
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${className}
      `}
      {...props}
    >
      {loading ? (
        <Spinner size={size === 'sm' ? 12 : 16} />
      ) : Icon ? (
        <Icon size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} />
      ) : null}
      {children}
      {iconRight && !loading && <iconRight size={size === 'sm' ? 14 : 16} />}
    </button>
  )
}
