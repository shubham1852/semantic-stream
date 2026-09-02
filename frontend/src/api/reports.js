/**
 * api/reports.js
 * Report list and PDF download endpoints.
 */

import client from './client'

/**
 * Fetch the list of all generated reports.
 * GET /api/v1/history   (reports are listed as part of session history)
 * @returns {Promise<{ sessions: Array }>}
 */
export async function getReports(limit = 50, offset = 0) {
  return client.get('/history', { params: { limit, offset } })
}

/**
 * Download a PDF report for a completed analysis session.
 * GET /api/v1/report/{session_id}
 * Returns a Blob — caller should create an object URL for download.
 * @param {string} sessionId
 * @returns {Promise<Blob>}
 */
export async function downloadReport(sessionId) {
  const response = await client.get(`/report/${sessionId}`, {
    responseType: 'blob',
    // Bypass the envelope unwrapper for binary responses
    transformResponse: [(data) => data],
  })
  return response
}

/**
 * Trigger server-side PDF generation for a session (if not already generated).
 * GET /api/v1/report/{session_id} with generate=true flag.
 * @param {string} sessionId
 * @returns {Promise<Blob>}
 */
export async function generateAndDownloadReport(sessionId) {
  const response = await client.get(`/report/${sessionId}`, {
    params: { generate: true },
    responseType: 'blob',
    transformResponse: [(data) => data],
  })
  return response
}
