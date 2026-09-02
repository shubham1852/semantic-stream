/**
 * api/videos.js
 * Video upload and history endpoints.
 */

import client from './client'

/**
 * Upload a video file.
 * POST /api/v1/upload
 * @param {File} file
 * @param {(pct: number) => void} [onProgress]
 * @returns {Promise<{ video_id: string, filename: string, duration_s: number, ... }>}
 */
export async function uploadVideo(file, onProgress) {
  const formData = new FormData()
  formData.append('file', file)

  return client.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) {
        onProgress(Math.round((evt.loaded / evt.total) * 100))
      }
    },
  })
}

/**
 * Fetch paginated history of analysis sessions.
 * GET /api/v1/history
 * @param {number} [limit=20]
 * @param {number} [offset=0]
 * @returns {Promise<{ sessions: Array }>}
 */
export async function getHistory(limit = 20, offset = 0) {
  return client.get('/history', { params: { limit, offset } })
}
