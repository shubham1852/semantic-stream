/**
 * pages/NotFoundPage.jsx
 * 404 page with animated back-home button.
 */

import { useNavigate } from 'react-router-dom'
import { Home, AlertTriangle } from 'lucide-react'
import Button from '../components/ui/Button'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 animate-fade-in">
      <div
        className="w-24 h-24 rounded-full flex items-center justify-center"
        style={{ background: 'rgba(79,70,229,0.1)', border: '1px solid rgba(79,70,229,0.2)' }}
      >
        <AlertTriangle size={40} className="text-data-amber" />
      </div>

      <div className="text-center space-y-2">
        <h1 className="font-display text-6xl font-bold gradient-text">404</h1>
        <p className="font-display text-xl font-semibold text-text-primary">Page Not Found</p>
        <p className="text-text-muted text-sm">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
      </div>

      <Button icon={Home} onClick={() => navigate('/')}>
        Back to Dashboard
      </Button>
    </div>
  )
}
