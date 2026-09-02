/**
 * hooks/useExperimentPoller.js
 * Polls GET /api/v1/experiment/{experimentId}/results every 3s
 * until the experiment reaches a terminal state.
 */

import { useEffect, useRef, useState } from 'react'
import { getExperimentResults } from '../api/experiments'

const TERMINAL_STATUSES = new Set(['done', 'complete', 'completed', 'error', 'failed'])
const POLL_INTERVAL_MS = 3000

/**
 * @param {string|null} experimentId — pass null to disable polling
 * @returns {{ status: string, results: object|null, winner: string|null, error: string|null }}
 */
export function useExperimentPoller(experimentId) {
  const [state, setState] = useState({
    status: 'idle',
    results: null,
    winner: null,
    error: null,
  })
  const timerRef = useRef(null)

  useEffect(() => {
    if (!experimentId) return

    const poll = async () => {
      try {
        const data = await getExperimentResults(experimentId)
        const strategies = data.strategies ?? {}
        const winner = data.winner ?? null

        // Determine status from the data shape
        const isDone = Object.keys(strategies).length > 0
        const status = isDone ? 'done' : 'running'

        setState({ status, results: strategies, winner, error: null })

        if (!TERMINAL_STATUSES.has(status)) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch (err) {
        // 404 / not ready yet → keep polling
        if (err.message?.includes('404') || err.message?.includes('not found')) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS)
        } else {
          setState((s) => ({ ...s, status: 'error', error: err.message }))
        }
      }
    }

    // Start polling after initial delay
    timerRef.current = setTimeout(poll, 1500)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [experimentId])

  return state
}
