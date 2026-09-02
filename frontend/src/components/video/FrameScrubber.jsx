/**
 * components/video/FrameScrubber.jsx
 * Frame-by-frame navigation slider for the AnalyticsPage.
 * Shows frame number, timestamp, and triggers frame fetch on change.
 */

import { useCallback } from 'react'
import { ChevronLeft, ChevronRight, SkipBack, SkipForward } from 'lucide-react'

function formatTimestamp(frameIndex, fps = 30) {
  const totalMs = (frameIndex / fps) * 1000
  const m = Math.floor(totalMs / 60000)
  const s = Math.floor((totalMs % 60000) / 1000)
  const ms = Math.floor(totalMs % 1000)
  return `${m}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`
}

/**
 * @param {{
 *   frame: number,
 *   totalFrames: number,
 *   fps?: number,
 *   onChange: (frame: number) => void,
 * }} props
 */
export default function FrameScrubber({
  frame = 0,
  totalFrames = 0,
  fps = 30,
  onChange,
  className = '',
}) {
  const clamp = useCallback(
    (v) => Math.max(0, Math.min(totalFrames - 1, v)),
    [totalFrames]
  )

  const seek = useCallback((v) => onChange?.(clamp(v)), [clamp, onChange])

  if (totalFrames === 0) return null

  return (
    <div className={`w-full ${className}`}>
      {/* Frame slider */}
      <input
        type="range"
        min={0}
        max={totalFrames - 1}
        step={1}
        value={frame}
        onChange={(e) => seek(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer mb-3"
        style={{
          background: `linear-gradient(to right,
            rgba(79,70,229,0.8) 0%, rgba(79,70,229,0.8) ${(frame / (totalFrames - 1)) * 100}%,
            rgba(79,70,229,0.15) ${(frame / (totalFrames - 1)) * 100}%, rgba(79,70,229,0.15) 100%)`,
        }}
      />

      {/* Controls row */}
      <div className="flex items-center justify-between">
        {/* Step buttons */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => seek(0)}
            className="text-text-muted hover:text-accent-light transition-colors p-1 rounded"
            title="First frame"
          >
            <SkipBack size={14} />
          </button>
          <button
            onClick={() => seek(frame - 1)}
            disabled={frame === 0}
            className="text-text-muted hover:text-accent-light transition-colors p-1 rounded disabled:opacity-30"
            title="Previous frame"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={() => seek(frame + 1)}
            disabled={frame >= totalFrames - 1}
            className="text-text-muted hover:text-accent-light transition-colors p-1 rounded disabled:opacity-30"
            title="Next frame"
          >
            <ChevronRight size={16} />
          </button>
          <button
            onClick={() => seek(totalFrames - 1)}
            className="text-text-muted hover:text-accent-light transition-colors p-1 rounded"
            title="Last frame"
          >
            <SkipForward size={14} />
          </button>
        </div>

        {/* Frame counter + timestamp */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted font-mono">
            {formatTimestamp(frame, fps)}
          </span>
          <span className="text-xs font-mono text-accent-light tabular-nums">
            {frame + 1}
            <span className="text-text-muted"> / {totalFrames}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
