/**
 * components/video/DetectionOverlay.jsx
 * Renders bounding boxes and priority tier labels on a canvas
 * overlaid on top of a video frame.
 */

import { useEffect, useRef } from 'react'

// Color per priority tier — matches heatmap colors
const TIER_COLORS = {
  P1: '#00FF87', // bright green — highest priority (face/person)
  P2: '#22D3EE', // cyan — text overlays
  P3: '#F59E0B', // amber — motion
  P4: '#F97316', // orange — objects
  P5: '#6B7280', // grey — background
}

/**
 * @param {{ detections: Array<{ bbox?: [number, number, number, number], x1?: number, y1?: number, x2?: number, y2?: number, class_name: string, priority_tier: string, confidence: number }>,
 *            width: number, height: number, className?: string }} props
 */
export default function DetectionOverlay({ detections = [], width = 640, height = 480, className = '' }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, width, height)

    detections.forEach((det) => {
      let x1 = 0
      let y1 = 0
      let w = 0
      let h = 0

      if (det.x1 !== undefined && det.x2 !== undefined && det.y1 !== undefined && det.y2 !== undefined) {
        x1 = det.x1
        y1 = det.y1
        w = det.x2 - det.x1
        h = det.y2 - det.y1
      } else if (Array.isArray(det.bbox) && det.bbox.length === 4) {
        const [b0, b1, b2, b3] = det.bbox
        x1 = b0
        y1 = b1
        w = b2
        h = b3
      }

      if (w <= 0 || h <= 0) return

      const tier = (det.priority_tier ?? 'P4').toUpperCase().replace('TIER_', '')
      const color = TIER_COLORS[tier] || '#F97316'
      const label = `${det.class_name ?? 'object'} · ${tier} (${Math.round((det.confidence ?? 0) * 100)}%)`

      // Draw colored bounding box
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, w, h)

      // Draw label background pill
      ctx.font = '11px JetBrains Mono, monospace'
      const textMetrics = ctx.measureText(label)
      const labelW = textMetrics.width + 10
      const labelH = 20
      const labelY = Math.max(labelH, y1)

      ctx.fillStyle = color
      ctx.fillRect(x1, labelY - labelH, labelW, labelH)

      // Draw label text
      ctx.fillStyle = '#000000'
      ctx.fillText(label, x1 + 5, labelY - 5)
    })
  }, [detections, width, height])

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className={`absolute inset-0 pointer-events-none ${className}`}
    />
  )
}

