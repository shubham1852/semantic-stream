/**
 * pages/ReportsPage.jsx
 * Lists all generated analysis sessions with PDF download buttons.
 * Shows a preview panel when a report is selected.
 */

import { useState, useEffect, useCallback } from 'react'
import { FileText, Download, Eye, RefreshCw, AlertCircle, Calendar, Film } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { StatusBadge } from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'
import { getReports, generateAndDownloadReport } from '../api/reports'

/* ─── Helper: trigger browser file download from Blob ─────── */
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/* ─── Report row ─────────────────────────────────────────── */
function ReportRow({ session, selected, onSelect, onDownload, downloading }) {
  const isSelected = selected?.session_id === session.session_id
  return (
    <tr
      className={`transition-colors cursor-pointer ${isSelected ? 'bg-accent/8' : 'hover:bg-white/3'}`}
      onClick={() => onSelect(session)}
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <Film size={14} className="text-text-muted shrink-0" />
          <span className="text-sm text-text-primary font-medium truncate max-w-[180px]">
            {session.filename ?? session.session_id}
          </span>
        </div>
      </td>
      <td className="px-4 py-3">
        <span className="text-xs font-mono text-text-muted">
          {session.bandwidth_profile ?? '—'}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="font-mono text-sm text-data-green">
          {session.spqi != null ? session.spqi.toFixed(4) : '—'}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="font-mono text-sm text-data-amber">
          {session.bitrate_reduction != null ? `${session.bitrate_reduction.toFixed(1)}%` : '—'}
        </span>
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={session.status ?? 'done'} />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5 text-xs text-text-muted">
          <Calendar size={11} />
          {session.created_at ? new Date(session.created_at).toLocaleDateString() : '—'}
        </div>
      </td>
      <td className="px-4 py-3">
        <Button
          size="sm"
          variant="ghost"
          loading={downloading === session.session_id}
          icon={<Download size={13} />}
          onClick={(e) => { e.stopPropagation(); onDownload(session) }}
        >
          PDF
        </Button>
      </td>
    </tr>
  )
}

/* ─── Main ─────────────────────────────────────────────────── */
export default function ReportsPage() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [downloading, setDownloading] = useState(null)

  const fetchReports = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getReports()
      setSessions(data?.sessions ?? [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchReports() }, [fetchReports])

  const handleDownload = useCallback(async (session) => {
    setDownloading(session.session_id)
    try {
      const blob = await generateAndDownloadReport(session.session_id)
      downloadBlob(blob, `semanticstream-report-${session.session_id.slice(0, 8)}.pdf`)
    } catch (e) {
      console.error('Download failed:', e)
    } finally {
      setDownloading(null)
    }
  }, [])

  return (
    <PageShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-display text-2xl font-bold text-text-primary">Reports</h1>
            <p className="text-sm text-text-muted mt-1">
              Download auto-generated PDF reports for any analysis session
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={14} />}
            loading={loading}
            onClick={fetchReports}
          >
            Refresh
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Sessions table */}
          <div className="lg:col-span-2">
            <Card className="overflow-hidden p-0">
              {loading ? (
                <div className="flex items-center justify-center h-48 gap-3">
                  <Spinner size={24} />
                  <span className="text-sm text-text-muted">Loading reports…</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center h-48 gap-3">
                  <AlertCircle size={32} className="text-data-red" />
                  <p className="text-sm text-text-muted">{error}</p>
                  <Button size="sm" variant="ghost" onClick={fetchReports}>Retry</Button>
                </div>
              ) : sessions.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 gap-3">
                  <FileText size={36} className="text-text-muted" />
                  <p className="text-text-muted font-medium">No sessions yet</p>
                  <p className="text-sm text-text-muted">Upload and analyze a video to generate a report.</p>
                  <a href="/upload" className="btn-primary px-4 py-1.5 rounded-btn text-sm">Start Analysis</a>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="data-table w-full">
                    <thead>
                      <tr>
                        <th>Video</th>
                        <th>Profile</th>
                        <th>SPQI</th>
                        <th>BR Saved</th>
                        <th>Status</th>
                        <th>Date</th>
                        <th>Report</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((s) => (
                        <ReportRow
                          key={s.session_id}
                          session={s}
                          selected={selected}
                          onSelect={setSelected}
                          onDownload={handleDownload}
                          downloading={downloading}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>

          {/* Preview panel */}
          <div>
            {selected ? (
              <Card className="p-5 space-y-4">
                <div className="flex items-center gap-2 mb-1">
                  <FileText size={16} className="text-accent-light" />
                  <Card.Title>Report Preview</Card.Title>
                </div>

                {/* Session meta */}
                <div className="space-y-2 text-sm">
                  {[
                    { label: 'Session ID', value: selected.session_id?.slice(0, 16) + '…' },
                    { label: 'Video',      value: selected.filename ?? '—' },
                    { label: 'Profile',    value: selected.bandwidth_profile ?? '—' },
                    { label: 'SPQI',       value: selected.spqi?.toFixed(4) ?? '—', green: true },
                    { label: 'BR Saved',   value: selected.bitrate_reduction != null ? `${selected.bitrate_reduction.toFixed(1)}%` : '—', green: true },
                  ].map(({ label, value, green }) => (
                    <div key={label} className="flex justify-between">
                      <span className="text-text-muted">{label}</span>
                      <span className={`font-mono text-xs ${green ? 'text-data-green' : 'text-text-primary'}`}>{value}</span>
                    </div>
                  ))}
                </div>

                {/* Report pages list */}
                <div className="border-t border-border-subtle pt-3">
                  <p className="text-xs text-text-muted mb-2 font-medium">PDF Contents</p>
                  {[
                    'Page 1 — Session Metadata',
                    'Page 2 — Strategy Comparison Table',
                    'Page 3 — Auto-generated Conclusion',
                    'Page 4 — SPQI & Bitrate Charts',
                    'Page 5 — SPQI & SEES Formulas',
                    'Page 6 — References',
                  ].map((page) => (
                    <div key={page} className="text-xs text-text-muted py-1 border-b border-border-subtle/50 last:border-0 flex items-center gap-2">
                      <Eye size={10} className="text-accent-light shrink-0" />
                      {page}
                    </div>
                  ))}
                </div>

                <Button
                  className="w-full"
                  icon={<Download size={16} />}
                  loading={downloading === selected.session_id}
                  onClick={() => handleDownload(selected)}
                >
                  Download PDF
                </Button>
              </Card>
            ) : (
              <Card className="p-8 flex flex-col items-center justify-center text-center gap-3">
                <FileText size={36} className="text-text-muted" />
                <p className="text-sm text-text-muted">
                  Select a session from the table to preview its report
                </p>
              </Card>
            )}
          </div>
        </div>
      </div>
    </PageShell>
  )
}
