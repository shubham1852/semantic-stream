/**
 * pages/HistoryPage.jsx
 * Paginated list of all past analysis sessions.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { History, ArrowRight, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'
import { getHistory } from '../api/videos'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { StatusBadge } from '../components/ui/Badge'
import Spinner from '../components/ui/Spinner'

const PAGE_SIZE = 15

export default function HistoryPage() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)

  const fetchPage = async (p) => {
    setLoading(true)
    try {
      const data = await getHistory(PAGE_SIZE, p * PAGE_SIZE)
      const items = data?.sessions ?? []
      setSessions(items)
      setHasMore(items.length === PAGE_SIZE)
    } catch {
      setSessions([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchPage(page) }, [page])

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <History size={22} className="text-accent-light" />
          <div>
            <h2 className="font-display text-xl font-bold text-text-primary">Analysis History</h2>
            <p className="text-text-muted text-sm mt-0.5">All past analysis sessions</p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={RefreshCw}
          onClick={() => fetchPage(page)}
          loading={loading}
        >
          Refresh
        </Button>
      </div>

      <Card padding={false}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner size={28} />
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center py-16 gap-4">
            <History size={36} className="text-text-muted" />
            <p className="text-text-muted text-sm">No analysis sessions found</p>
            <Button size="sm" onClick={() => navigate('/upload')}>Upload a Video</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="pl-6">Video</th>
                  <th>Job ID</th>
                  <th>Strategy</th>
                  <th>Avg SSIM</th>
                  <th>Avg PSNR</th>
                  <th>Status</th>
                  <th>Date</th>
                  <th className="pr-6"></th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => {
                  const jobId = s.job_id ?? s.id
                  return (
                    <tr
                      key={jobId}
                      className="cursor-pointer"
                      onClick={() => navigate(`/results/${jobId}`)}
                    >
                      <td className="pl-6 font-mono text-xs text-text-primary max-w-[200px] truncate">
                        {s.filename ?? s.video_id ?? '—'}
                      </td>
                      <td className="font-mono text-xs text-text-muted">
                        {jobId?.slice(0, 8)}…
                      </td>
                      <td className="text-sm text-text-muted">
                        {s.strategy ?? 'semanticstream'}
                      </td>
                      <td className="font-mono text-sm text-data-green">
                        {s.avg_ssim?.toFixed(3) ?? '—'}
                      </td>
                      <td className="font-mono text-sm text-data-blue">
                        {s.avg_psnr ? `${s.avg_psnr.toFixed(1)} dB` : '—'}
                      </td>
                      <td><StatusBadge status={s.status ?? 'done'} /></td>
                      <td className="text-xs text-text-muted">
                        {s.created_at ? new Date(s.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="pr-6">
                        <ArrowRight size={14} className="text-text-muted" />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!loading && sessions.length > 0 && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-border-subtle">
            <span className="text-xs text-text-muted font-mono">
              Page {page + 1}
            </span>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                icon={ChevronLeft}
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Prev
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={!hasMore}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight size={14} className="ml-1" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
