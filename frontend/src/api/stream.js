/**
 * api/stream.js
 * Streaming endpoints — get HLS stream URL for a processed video,
 * and fetch the single-frame overlay endpoint.
 */

import client from './client'

/**
 * Build the HLS stream URL for a processed video.
 * The Vite proxy forwards /api → :8000, so this URL works in dev too.
 * @param {string} videoId
 * @returns {string}   e.g. "/api/v1/stream/abc123/playlist.m3u8"
 */
export function getStreamUrl(videoId) {
  return `/api/v1/stream/${videoId}/playlist.m3u8`
}

/**
 * Fetch a single frame with an optional visual overlay from the backend.
 * GET /api/v1/frame/{video_id}/{frame_number}?overlay=heatmap|original|compressed|sidebyside
 * @param {string} videoId
 * @param {number} frameNumber
 * @param {'heatmap'|'original'|'compressed'|'sidebyside'} [overlay='heatmap']
 * @returns {Promise<{
 *   frame_base64: string,
 *   priority_map_base64: string,
 *   detections: Array<{ label: string, confidence: number, bbox: number[], priority_tier: string, qp_assigned: number }>
 * }>}
 */
export async function getFrame(videoId, frameNumber, overlay = 'heatmap') {
  return client.get(`/frame/${videoId}/${frameNumber}`, {
    params: { overlay },
  })
}

/**
 * Check if a processed stream is ready for a given video.
 * GET /api/v1/stream/{video_id}/status
 * @param {string} videoId
 * @returns {Promise<{ ready: boolean, segment_count: number }>}
 */
export async function getStreamStatus(videoId) {
  return client.get(`/stream/${videoId}/status`)
}
