/**
 * components/video/DetectionOverlay.jsx
 * Renders bounding boxes, priority tier labels, and QP assignments on a canvas
 * overlaid on top of a video frame.
 */

import { useEffect, useRef } from 'react'

// Color per priority tier — matches heatmap and research specs
const TIER_COLORS = {
  P1: '#00FF87', // bright emerald green — highest priority (face/person)
  P2: '#22D3EE', // cyan — text overlays
  P3: '#F59E0B', // amber — motion
  P4: '#818CF8', // electric indigo / orange — objects
  P5: '#6B7280', // grey — background
}

const TIER_QP = {
  P1: 18,
  P2: 24,
  P3: 26,
  P4: 28,
  P5: 42,
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

      const rawTier = (det.priority_tier ?? 'P4').toUpperCase().replace('TIER_', '')
      const tier = rawTier.startsWith('P') ? rawTier : `P${rawTier}`
      const color = TIER_COLORS[tier] || '#00FF87'
      const qp = TIER_QP[tier] || 28
      const name = (det.class_name ?? 'object').toUpperCase()
      const conf = Math.round((det.confidence ?? 0) * 100)
      const label = `${tier} ${name} · QP ${qp} · ${conf}%`

      // 1. Draw bounding box with subtle corner brackets
      ctx.save()
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, w, h)

      // Corner accent brackets (high-tech HUD look)
      const bracketLen = Math.min(12, Math.min(w, h) / 4)
      ctx.lineWidth = 3.5
      // Top-left
      ctx.beginPath()
      ctx.moveTo(x1, y1 + bracketLen)
      ctx.lineTo(x1, y1)
      ctx.lineTo(x1 + bracketLen, y1)
      ctx.stroke()
      // Top-right
      ctx.beginPath()
      ctx.moveTo(x1 + w - bracketLen, y1)
      ctx.lineTo(x1 + w, y1)
      ctx.lineTo(x1 + w, y1 + bracketLen)
      ctx.stroke()
      // Bottom-left
      ctx.beginPath()
      ctx.moveTo(x1, y1 + h - bracketLen)
      ctx.lineTo(x1, y1 + h)
      ctx.lineTo(x1 + bracketLen, y1 + h)
      ctx.stroke()
      // Bottom-right
      ctx.beginPath()
      ctx.moveTo(x1 + w - bracketLen, y1 + h)
      ctx.lineTo(x1 + w, y1 + h)
      ctx.lineTo(x1 + w, y1 + h - bracketLen)
      ctx.stroke()
      ctx.restore()

      // 2. Draw label background pill
      ctx.font = 'bold 11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
      const textMetrics = ctx.measureText(label)
      const labelW = textMetrics.width + 14
      const labelH = 22
      const labelY = Math.max(labelH + 2, y1)

      // Dark background pill with colored border
      ctx.fillStyle = 'rgba(10, 14, 26, 0.88)'
      ctx.beginPath()
      ctx.roundRect(x1, labelY - labelH, labelW, labelH, 4)
      ctx.fill()
      ctx.strokeStyle = color
      ctx.lineWidth = 1.2
      ctx.stroke()

      // Small tier color indicator dot
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(x1 + 8, labelY - labelH / 2, 3.5, 0, 2 * Math.PI)
      ctx.fill()

      // Label text
      ctx.fillStyle = '#FFFFFF'
      ctx.fillText(label, x1 + 16, labelY - 7)
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
