/**
 * hooks/useJobPoller.js
 * Polls GET /api/v1/results/{jobId} every 2s while the job is not done.
 * Stops automatically when status is 'done' or 'error'.
 */

import { useEffect, useRef, useState } from 'react'
import { getResults } from '../api/analysis'

const TERMINAL_STATUSES = new Set(['done', 'error', 'failed', 'complete', 'completed'])
const POLL_INTERVAL_MS = 2000

/**
 * @param {string|null} jobId — pass null to disable polling
 * @returns {{ status: string, progressPct: number, metrics: object|null, error: string|null }}
 */
export function useJobPoller(jobId) {
  const [state, setState] = useState({
    status: 'idle',
    progressPct: 0,
    metrics: null,
    videoId: null,
    error: null,
  })
  const timerRef = useRef(null)

  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const data = await getResults(jobId)
        const status = data.status ?? 'running'
        const progressPct = data.progress_percent ?? 0
        const rawMetrics = data.metrics ?? {}
        const summary = data.summary ?? rawMetrics.summary ?? data
        const frameMetrics = data.frame_metrics ?? data.per_frame_metrics ?? rawMetrics.frame_metrics ?? rawMetrics.per_frame_metrics ?? []
        const metrics = {
          ...data,
          ...rawMetrics,
          summary,
          frame_metrics: frameMetrics,
          per_frame_metrics: frameMetrics,
        }
        const videoId = data.video_id ?? summary?.video_id ?? rawMetrics?.summary?.video_id ?? null

        setState({ status, progressPct, metrics, videoId, error: null })

        if (!TERMINAL_STATUSES.has(status.toLowerCase())) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch (err) {
        setState((s) => ({ ...s, status: 'error', error: err.message }))
      }
    }

    poll()

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [jobId])

  return state
}
