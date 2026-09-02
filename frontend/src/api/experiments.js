/**
 * api/experiments.js
 * Experiment (multi-strategy comparison) endpoints.
 */

import client from './client'

/**
 * Start a parallel multi-strategy experiment.
 * POST /api/v1/experiment
 * @param {{ video_id: string, strategies?: string[], bandwidth_profile?: string }} payload
 * @returns {Promise<{ experiment_id: string, status: string }>}
 */
export async function startExperiment(payload) {
  return client.post('/experiment', {
    video_id: payload.videoId,
    strategies: payload.strategies ?? ['uniform_abr', 'static_roi', 'semanticstream'],
    bandwidth_profile: payload.bandwidthProfile ?? 'strong_wifi',
  })
}

/**
 * Fetch results for a completed experiment.
 * GET /api/v1/experiment/{experiment_id}/results
 * @param {string} experimentId
 * @returns {Promise<{ experiment_id: string, strategies: object, winner: string|null }>}
 */
export async function getExperimentResults(experimentId) {
  return client.get(`/experiment/${experimentId}/results`)
}
