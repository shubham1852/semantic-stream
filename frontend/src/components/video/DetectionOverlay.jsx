/**
 * components/video/DetectionOverlay.jsx
 * Renders bounding boxes and priority tier labels on a canvas
 * overlaid on top of a video frame.
 */

import { useEffect, useRef } from 'react'

const TIER_COLORS = {
  P1: '#00FF87',
  P2: '#4ADE80',
  P3: '#F59E0B',
  P4: '#818CF8',
  P5: '#EF4444',
}

/**
 * @param {{ detections: Array<{ bbox: [x,y,w,h], class_name: string, priority_tier: string, confidence: number }>,
 *            width: number, height: number }} props
 */
export default function DetectionOverlay({ detections = [], width = 640, height = 480, className = '' }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, width, height)

    detections.forEach((det) => {
      const [x, y, w, h] = det.bbox ?? [0, 0, 0, 0]
      const tier = (det.priority_tier ?? 'P3').toUpperCase().replace('TIER_', '')
      const color = TIER_COLORS[tier] ?? '#818CF8'
      const label = `${det.class_name ?? '?'} · ${tier} (${((det.confidence ?? 0) * 100).toFixed(0)}%)`

      // Box
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.shadowColor = color
      ctx.shadowBlur = 8
      ctx.strokeRect(x, y, w, h)
      ctx.shadowBlur = 0

      // Label background
      ctx.font = '11px JetBrains Mono, monospace'
      const textWidth = ctx.measureText(label).width
      ctx.fillStyle = `${color}22`
      ctx.fillRect(x, y - 18, textWidth + 8, 18)

      // Label border
      ctx.strokeStyle = color
      ctx.lineWidth = 1
      ctx.strokeRect(x, y - 18, textWidth + 8, 18)

      // Label text
      ctx.fillStyle = color
      ctx.fillText(label, x + 4, y - 5)
    })
  }, [detections, width, height])

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className={`absolute inset-0 pointer-events-none ${className}`}
      style={{ mixBlendMode: 'screen' }}
    />
  )
}
