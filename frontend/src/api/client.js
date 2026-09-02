/**
 * api/client.js
 * Axios instance pre-configured for SemanticStream backend.
 * - baseURL points to /api/v1 (proxied by Vite to localhost:8000)
 * - Response interceptor unwraps the { status, data, message } envelope
 * - Error interceptor normalises error messages and fires a toast notification
 */

import axios from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120_000, // 2-minute timeout for large uploads / long analyses
})

// ── Response interceptor: unwrap envelope ────────────────────────────────────
client.interceptors.response.use(
  (response) => {
    // Backend always returns { status: 'success', data: {...}, message: '...' }
    // Unwrap so callers receive `data` directly
    if (response.data && response.data.status === 'success') {
      return response.data.data
    }
    return response.data
  },
  (error) => {
    // Normalise the error message from the backend envelope
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred'

    const status = error.response?.status

    // Fire a toast for non-polling errors (avoid spamming on repeated polls)
    // Import lazily to break circular dependency (store imports client)
    const isPollingRequest =
      error.config?.url?.includes('/results/') ||
      error.config?.url?.includes('/experiment/')

    if (!isPollingRequest && status !== 404) {
      try {
        // Dynamic import avoids circular dependency at module load time
        import('../store/useAppStore').then(({ default: useAppStore }) => {
          const addToast = useAppStore.getState().addToast
          if (typeof addToast === 'function') {
            addToast({
              type: 'error',
              message: `API Error ${status ? `(${status})` : ''}: ${message}`,
            })
          }
        }).catch(() => {/* store not yet initialised */})
      } catch {
        // Silently ignore — toast is best-effort
      }
    }

    return Promise.reject(new Error(message))
  }
)

export default client
