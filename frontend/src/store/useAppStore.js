/**
 * store/useAppStore.js
 * Zustand global state store with three slices:
 *   - upload  : video upload flow state
 *   - analysis: current analysis job state
 *   - experiment: current experiment state
 *   - ui      : sidebar, toasts
 */

import { create } from 'zustand'

const useAppStore = create((set, get) => ({
  // ── Upload Slice ─────────────────────────────────────────────────────────
  upload: {
    file: null,
    videoId: null,
    progress: 0,
    status: 'idle', // idle | uploading | done | error
    error: null,
    videoMeta: null,
  },
  setUploadFile: (file) =>
    set((s) => ({ upload: { ...s.upload, file, status: 'idle', error: null } })),
  setUploadProgress: (progress) =>
    set((s) => ({ upload: { ...s.upload, progress } })),
  setUploadDone: (videoId, videoMeta) =>
    set((s) => ({
      upload: { ...s.upload, status: 'done', videoId, videoMeta, progress: 100 },
    })),
  setUploadError: (error) =>
    set((s) => ({ upload: { ...s.upload, status: 'error', error } })),
  resetUpload: () =>
    set(() => ({
      upload: { file: null, videoId: null, progress: 0, status: 'idle', error: null, videoMeta: null },
    })),

  // ── Analysis Slice ───────────────────────────────────────────────────────
  analysis: {
    jobId: null,
    status: 'idle', // idle | queued | running | done | error
    progressPct: 0,
    metrics: null,
    error: null,
    config: {
      frameSampleRate: 5,
      confidenceThreshold: 0.45,
      bandwidthProfile: '',
      runComparison: false,
    },
  },
  setAnalysisConfig: (config) =>
    set((s) => ({ analysis: { ...s.analysis, config: { ...s.analysis.config, ...config } } })),
  setAnalysisQueued: (jobId) =>
    set((s) => ({ analysis: { ...s.analysis, jobId, status: 'queued', progressPct: 0 } })),
  setAnalysisProgress: (progressPct, status) =>
    set((s) => ({ analysis: { ...s.analysis, progressPct, status: status ?? s.analysis.status } })),
  setAnalysisDone: (metrics) =>
    set((s) => ({ analysis: { ...s.analysis, status: 'done', progressPct: 100, metrics } })),
  setAnalysisError: (error) =>
    set((s) => ({ analysis: { ...s.analysis, status: 'error', error } })),
  resetAnalysis: () =>
    set((s) => ({
      analysis: { ...s.analysis, jobId: null, status: 'idle', progressPct: 0, metrics: null, error: null },
    })),

  // ── Experiment Slice ─────────────────────────────────────────────────────
  experiment: {
    experimentId: null,
    status: 'idle', // idle | running | done | error
    results: null,
    error: null,
    config: {
      videoId: '',
      strategies: ['uniform_abr', 'static_roi', 'semanticstream'],
      bandwidthProfile: 'strong_wifi',
    },
  },
  setExperimentConfig: (config) =>
    set((s) => ({ experiment: { ...s.experiment, config: { ...s.experiment.config, ...config } } })),
  setExperimentRunning: (experimentId) =>
    set((s) => ({ experiment: { ...s.experiment, experimentId, status: 'running' } })),
  setExperimentDone: (results) =>
    set((s) => ({ experiment: { ...s.experiment, status: 'done', results } })),
  setExperimentError: (error) =>
    set((s) => ({ experiment: { ...s.experiment, status: 'error', error } })),
  resetExperiment: () =>
    set((s) => ({
      experiment: { ...s.experiment, experimentId: null, status: 'idle', results: null, error: null },
    })),

  // ── UI Slice ─────────────────────────────────────────────────────────────
  ui: {
    sidebarOpen: true,
    toasts: [],
  },
  toggleSidebar: () =>
    set((s) => ({ ui: { ...s.ui, sidebarOpen: !s.ui.sidebarOpen } })),
  addToast: (toast) => {
    const id = Date.now().toString()
    set((s) => ({
      ui: { ...s.ui, toasts: [...s.ui.toasts, { id, ...toast }] },
    }))
    // Auto-dismiss after 4s
    setTimeout(() => get().removeToast(id), 4000)
    return id
  },
  removeToast: (id) =>
    set((s) => ({
      ui: { ...s.ui, toasts: s.ui.toasts.filter((t) => t.id !== id) },
    })),
}))

export default useAppStore
