/**
 * components/layout/Sidebar.jsx
 * Collapsible left navigation sidebar — all 12 routes.
 */

import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  FlaskConical,
  Camera,
  History,
  ChevronLeft,
  ChevronRight,
  Radio,
  MonitorPlay,
  BarChart2,
  Wifi,
  FileText,
  Settings,
  BookOpen,
} from 'lucide-react'
import useAppStore from '../../store/useAppStore'

const NAV_ITEMS = [
  { to: '/dashboard',   icon: LayoutDashboard, label: 'Dashboard',       end: true },
  { to: '/upload',      icon: Upload,           label: 'Upload & Analyse' },
  { to: '/experiments', icon: FlaskConical,     label: 'Experiments' },
  { to: '/live',        icon: Camera,           label: 'Live Camera' },
  { to: '/streaming',   icon: MonitorPlay,      label: 'Streaming' },
  { to: '/analytics',   icon: BarChart2,        label: 'Analytics' },
  { to: '/bandwidth',   icon: Wifi,             label: 'Bandwidth' },
  { to: '/history',     icon: History,          label: 'History' },
  { to: '/reports',     icon: FileText,         label: 'Reports' },
  { to: '/research',    icon: BookOpen,         label: 'Research' },
  { to: '/settings',    icon: Settings,         label: 'Settings' },
]

export default function Sidebar() {
  const sidebarOpen  = useAppStore((s) => s.ui.sidebarOpen)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)

  return (
    <aside
      className={`
        relative flex flex-col shrink-0
        transition-all duration-300 ease-smooth
        ${sidebarOpen ? 'w-60' : 'w-16'}
      `}
      style={{
        background: 'rgba(10,14,26,0.85)',
        borderRight: '1px solid rgba(79,70,229,0.12)',
        backdropFilter: 'blur(12px)',
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-4 py-5 overflow-hidden">
        <div
          className="flex items-center justify-center shrink-0 w-8 h-8 rounded-lg"
          style={{ background: 'linear-gradient(135deg, #4F46E5, #00FF87)' }}
        >
          <Radio size={16} className="text-white" />
        </div>
        {sidebarOpen && (
          <span className="font-display font-bold text-sm text-text-primary whitespace-nowrap animate-fade-in">
            Semantic<span className="gradient-text">Stream</span>
          </span>
        )}
      </div>

      {/* Divider */}
      <div className="mx-4 mb-4 h-px" style={{ background: 'rgba(79,70,229,0.12)' }} />

      {/* Nav */}
      <nav className="flex-1 flex flex-col gap-1 px-2 overflow-y-auto">
        {NAV_ITEMS.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `
              flex items-center gap-3 px-3 py-2.5 rounded-btn text-sm font-medium
              transition-all duration-150
              ${isActive
                ? 'bg-accent/15 text-accent-light border border-accent/25'
                : 'text-text-muted hover:text-text-primary hover:bg-white/5 border border-transparent'
              }
              ${sidebarOpen ? '' : 'justify-center'}
            `}
            title={!sidebarOpen ? label : undefined}
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={18}
                  className={`shrink-0 ${isActive ? 'text-accent-light' : ''}`}
                />
                {sidebarOpen && (
                  <span className="whitespace-nowrap animate-fade-in">{label}</span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="px-2 pb-4">
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center justify-center py-2 rounded-btn text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
          title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {sidebarOpen
            ? <ChevronLeft size={18} />
            : <ChevronRight size={18} />
          }
        </button>
      </div>
    </aside>
  )
}
