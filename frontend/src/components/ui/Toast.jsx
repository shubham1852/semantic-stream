/**
 * components/ui/Toast.jsx
 * Toast notification system — ToastContainer renders all active toasts from Zustand store.
 */

import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Info, AlertTriangle, X } from 'lucide-react'
import useAppStore from '../../store/useAppStore'

const CONFIG = {
  success: { icon: CheckCircle, color: 'text-data-green', border: 'border-data-green/30', bg: 'bg-data-green/5' },
  error:   { icon: XCircle,     color: 'text-data-red',   border: 'border-data-red/30',   bg: 'bg-data-red/5' },
  info:    { icon: Info,        color: 'text-data-blue',  border: 'border-data-blue/30',  bg: 'bg-data-blue/5' },
  warning: { icon: AlertTriangle, color: 'text-data-amber', border: 'border-data-amber/30', bg: 'bg-data-amber/5' },
}

function ToastItem({ id, type = 'info', title, message }) {
  const removeToast = useAppStore((s) => s.removeToast)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    // Trigger entrance animation
    requestAnimationFrame(() => setVisible(true))
  }, [])

  const cfg = CONFIG[type] ?? CONFIG.info
  const Icon = cfg.icon

  return (
    <div
      className={`
        flex items-start gap-3 p-4 rounded-card border glass-card
        ${cfg.border} ${cfg.bg}
        transition-all duration-300
        ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}
      `}
      style={{ minWidth: 280, maxWidth: 360 }}
    >
      <Icon size={18} className={`${cfg.color} mt-0.5 shrink-0`} />
      <div className="flex-1 min-w-0">
        {title && <p className="text-sm font-semibold text-text-primary">{title}</p>}
        {message && <p className="text-xs text-text-muted mt-0.5">{message}</p>}
      </div>
      <button
        onClick={() => removeToast(id)}
        className="text-text-muted hover:text-text-primary transition-colors shrink-0"
      >
        <X size={14} />
      </button>
    </div>
  )
}

export function ToastContainer() {
  const toasts = useAppStore((s) => s.ui.toasts)

  return (
    <div
      className="fixed bottom-6 right-6 flex flex-col gap-3 z-50"
      aria-live="polite"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} {...toast} />
      ))}
    </div>
  )
}

export default ToastItem
