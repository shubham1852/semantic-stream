/**
 * ErrorBoundary.jsx
 * =================
 * React class-based error boundary for SemanticStream.
 *
 * Catches any uncaught runtime errors in the component tree below it
 * and renders a styled fallback UI instead of a blank screen.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <App />
 *   </ErrorBoundary>
 */

import { Component } from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    this.setState({ info })
    console.error('[SemanticStream] Unhandled error caught by ErrorBoundary:', error, info)
  }

  _reset = () => {
    this.setState({ hasError: false, error: null, info: null })
    window.location.href = '/dashboard'
  }

  render() {
    if (!this.state.hasError) return this.props.children

    const { error } = this.state

    return (
      <div
        id="error-boundary-fallback"
        style={{
          minHeight: '100vh',
          background: '#0A0E1A',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'Inter, sans-serif',
          padding: '2rem',
        }}
      >
        <div
          style={{
            maxWidth: 520,
            width: '100%',
            background: '#151C34',
            border: '1px solid rgba(239,68,68,0.35)',
            borderRadius: 16,
            padding: '2.5rem',
            textAlign: 'center',
          }}
        >
          {/* Icon */}
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              background: 'rgba(239,68,68,0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.5rem',
            }}
          >
            <AlertTriangle size={36} color="#EF4444" />
          </div>

          {/* Title */}
          <h1
            style={{
              fontFamily: 'Space Grotesk, sans-serif',
              fontSize: '1.5rem',
              fontWeight: 700,
              color: '#F0F0FF',
              marginBottom: '0.5rem',
            }}
          >
            Something went wrong
          </h1>

          <p style={{ color: '#8892A4', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
            SemanticStream encountered an unexpected error.
            <br />
            Your analysis data is safe — this is a UI error only.
          </p>

          {/* Error details */}
          {error && (
            <div
              style={{
                background: '#0A0E1A',
                border: '1px solid rgba(239,68,68,0.2)',
                borderRadius: 8,
                padding: '0.75rem 1rem',
                marginBottom: '1.5rem',
                textAlign: 'left',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: '0.78rem',
                color: '#EF4444',
                overflowX: 'auto',
                maxHeight: 120,
                overflowY: 'auto',
              }}
            >
              {error.message || String(error)}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
            <button
              id="error-boundary-retry-btn"
              onClick={() => window.location.reload()}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.6rem 1.2rem',
                background: 'rgba(79,70,229,0.15)',
                border: '1px solid rgba(79,70,229,0.4)',
                borderRadius: 8,
                color: '#818CF8',
                fontSize: '0.85rem',
                cursor: 'pointer',
                fontFamily: 'Space Grotesk, sans-serif',
                fontWeight: 600,
              }}
            >
              <RefreshCw size={15} />
              Reload Page
            </button>

            <button
              id="error-boundary-home-btn"
              onClick={this._reset}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.6rem 1.2rem',
                background: 'linear-gradient(135deg, #4F46E5, #7C3AED)',
                border: 'none',
                borderRadius: 8,
                color: '#fff',
                fontSize: '0.85rem',
                cursor: 'pointer',
                fontFamily: 'Space Grotesk, sans-serif',
                fontWeight: 600,
              }}
            >
              <Home size={15} />
              Back to Dashboard
            </button>
          </div>

          <p
            style={{
              marginTop: '1.5rem',
              fontSize: '0.75rem',
              color: 'rgba(136,146,164,0.6)',
            }}
          >
            SemanticStream v1.0.0 · VIT BITE314L
          </p>
        </div>
      </div>
    )
  }
}
