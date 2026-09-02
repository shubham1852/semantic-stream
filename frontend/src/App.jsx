/**
 * App.jsx
 * Top-level React Router v6 route tree.
 * - LandingPage ("/") is standalone (no Sidebar/Topbar)
 * - All other routes share the PageShell layout (Sidebar + Topbar)
 * - ErrorBoundary wraps all routes to catch unhandled runtime errors
 */

import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import PageShell from './components/layout/PageShell'
import ErrorBoundary from './components/ui/ErrorBoundary'

// Standalone page (no shell)
import LandingPage     from './pages/LandingPage'

// Shell pages
import DashboardPage   from './pages/DashboardPage'
import UploadPage      from './pages/UploadPage'
import ResultsPage     from './pages/ResultsPage'
import ExperimentPage  from './pages/ExperimentPage'
import LivePage        from './pages/LivePage'
import HistoryPage     from './pages/HistoryPage'
import StreamingPage   from './pages/StreamingPage'
import AnalyticsPage   from './pages/AnalyticsPage'
import BandwidthPage   from './pages/BandwidthPage'
import ReportsPage     from './pages/ReportsPage'
import SettingsPage    from './pages/SettingsPage'
import ResearchPage    from './pages/ResearchPage'
import NotFoundPage    from './pages/NotFoundPage'

export default function App() {
  // wsConnected is lifted here so Topbar can show the live indicator
  // when the user is on the Live page. LivePage updates this via callback.
  const [wsConnected, setWsConnected] = useState(false)

  return (
    <ErrorBoundary>
      <Routes>
        {/* ── Standalone route — no Sidebar/Topbar ── */}
        <Route path="/" element={<LandingPage />} />

        {/* ── Shell routes ── */}
        <Route element={<PageShell wsConnected={wsConnected} />}>
          <Route path="/dashboard"           element={<DashboardPage />} />
          <Route path="/upload"              element={<UploadPage />} />
          <Route path="/results/:jobId"      element={<ResultsPage />} />
          <Route path="/experiments"         element={<ExperimentPage />} />
          <Route path="/live"                element={<LivePage onWsChange={setWsConnected} />} />
          <Route path="/history"             element={<HistoryPage />} />
          <Route path="/streaming/:videoId"  element={<StreamingPage />} />
          <Route path="/streaming"           element={<StreamingPage />} />
          <Route path="/analytics"           element={<AnalyticsPage />} />
          <Route path="/bandwidth"           element={<BandwidthPage />} />
          <Route path="/reports"             element={<ReportsPage />} />
          <Route path="/settings"            element={<SettingsPage />} />
          <Route path="/research"            element={<ResearchPage />} />
          <Route path="*"                    element={<NotFoundPage />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}
