/**
 * api/analysis.js
 * Analysis job endpoints — queue a job and poll for results.
 */

import client from './client'

/**
 * Queue an analysis job for an uploaded video.
 * POST /api/v1/analyze/{video_id}
 * @param {string} videoId
 * @param {{ frame_sample_rate?: number, confidence_threshold?: number, bandwidth_profile?: string, run_comparison?: boolean }} config
 * @returns {Promise<{ job_id: string, status: string, estimated_time_seconds: number }>}
 */
export async function startAnalysis(videoId, config = {}) {
  return client.post(`/analyze/${videoId}`, {
    frame_sample_rate: config.frameSampleRate ?? 5,
    confidence_threshold: config.confidenceThreshold ?? 0.45,
    bandwidth_profile: config.bandwidthProfile ?? null,
    run_comparison: config.runComparison ?? false,
  })
}

/**
 * Get status and metrics for an analysis job.
 * GET /api/v1/results/{job_id}
 * @param {string} jobId
 * @returns {Promise<{ job_id: string, status: string, progress_percent: number, metrics: object|null }>}
 */
export async function getResults(jobId) {
  return client.get(`/results/${jobId}`)
}
