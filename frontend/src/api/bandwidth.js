/**
 * api/bandwidth.js
 * Bandwidth simulation profile endpoints.
 */

import client from './client'

/**
 * Fetch all available bandwidth simulation profiles.
 * GET /api/v1/bandwidth-profiles
 * @returns {Promise<{ profiles: Record<string, number[]> }>}
 */
export async function getBandwidthProfiles() {
  return client.get('/bandwidth-profiles')
}
