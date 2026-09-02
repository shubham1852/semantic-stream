/**
 * components/video/HeatmapOverlay.jsx
 * D3-powered canvas overlay that renders the semantic priority heatmap
 * on top of a video element. Uses the priority_map_base64 from the backend.
 *
 * Color mapping (matches TIER_COLORS across the codebase):
 *   1.0 → #00FF87 (P1 face)  |  0.1 → #EF4444 (P5 background)
 * Intermediate values are interpolated on a green→amber→red gradient.
 */

import { useEffect, useRef } from 'react'

/** Map a priority value [0, 1] to an RGBA array. */
function priorityToRgba(value, alpha = 0.55) {
  // value: 1.0 = green (#00FF87), 0.6 = amber (#F59E0B), 0.1 = red (#EF4444)
  let r, g, b
  if (value >= 0.6) {
    // green → amber  (1.0 → 0.6)
    const t = (value - 0.6) / 0.4
    r = Math.round(245 + t * (0 - 245))
    g = Math.round(158 + t * (255 - 158))
    b = Math.round(11 + t * (135 - 11))
  } else {
    // amber → red  (0.6 → 0.0)
    const t = (value - 0.1) / 0.5
    r = Math.round(239 + t * (245 - 239))
    g = Math.round(68 + t * (158 - 68))
    b = Math.round(68 + t * (11 - 68))
  }
  return [Math.max(0, Math.min(255, r)), Math.max(0, Math.min(255, g)), Math.max(0, Math.min(255, b)), Math.round(alpha * 255)]
}

/**
 * @param {{
 *   priorityMapBase64: string|null,  // base64-encoded grayscale PNG from backend
 *   width: number,
 *   height: number,
 *   opacity?: number,
 * }} props
 */
export default function HeatmapOverlay({
  priorityMapBase64 = null,
  width = 640,
  height = 480,
  opacity = 0.55,
  className = '',
}) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!priorityMapBase64 || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')

    const img = new Image()
    img.onload = () => {
      // Draw the greyscale priority map onto an offscreen canvas to read pixel data
      const offscreen = document.createElement('canvas')
      offscreen.width = img.naturalWidth
      offscreen.height = img.naturalHeight
      const octx = offscreen.getContext('2d')
      octx.drawImage(img, 0, 0)

      const sourceData = octx.getImageData(0, 0, offscreen.width, offscreen.height)
      const output = ctx.createImageData(canvas.width, canvas.height)

      const scaleX = offscreen.width / canvas.width
      const scaleY = offscreen.height / canvas.height

      for (let y = 0; y < canvas.height; y++) {
        for (let x = 0; x < canvas.width; x++) {
          const srcX = Math.floor(x * scaleX)
          const srcY = Math.floor(y * scaleY)
          const srcIdx = (srcY * offscreen.width + srcX) * 4
          // Greyscale value (R channel) → priority [0, 1]
          const priority = sourceData.data[srcIdx] / 255
          const [r, g, b, a] = priorityToRgba(priority, opacity)
          const dstIdx = (y * canvas.width + x) * 4
          output.data[dstIdx]     = r
          output.data[dstIdx + 1] = g
          output.data[dstIdx + 2] = b
          output.data[dstIdx + 3] = a
        }
      }
      ctx.putImageData(output, 0, 0)
    }
    img.src = `data:image/png;base64,${priorityMapBase64}`
  }, [priorityMapBase64, width, height, opacity])

  // Clear canvas if no data
  useEffect(() => {
    if (!priorityMapBase64 && canvasRef.current) {
      canvasRef.current.getContext('2d').clearRect(0, 0, width, height)
    }
  }, [priorityMapBase64, width, height])

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className={`absolute inset-0 pointer-events-none ${className}`}
    />
  )
}
