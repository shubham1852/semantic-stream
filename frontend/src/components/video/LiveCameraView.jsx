/**
 * components/video/LiveCameraView.jsx
 * Webcam capture → WebSocket → priority heatmap side-by-side view.
 * Left: raw webcam feed with detection bounding boxes.
 * Right: priority heatmap returned by the server.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useWebSocket } from '../../hooks/useWebSocket'
import DetectionOverlay from './DetectionOverlay'
import { Camera, CameraOff, Zap, Eye } from 'lucide-react'

const FRAME_INTERVAL_MS = 80 // ~12 fps to server

export default function LiveCameraView({ onConnectionChange }) {
  const videoRef = useRef(null)
  const captureCanvasRef = useRef(null)
  const streamRef = useRef(null)
  const frameTimerRef = useRef(null)

  const [cameraOn, setCameraOn] = useState(false)
  const dimensions = { width: 640, height: 480 }

  const { isConnected, lastFrame, error, connect, disconnect, sendFrame } = useWebSocket()

  useEffect(() => {
    onConnectionChange?.(isConnected)
  }, [isConnected, onConnectionChange])

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
      }
      setCameraOn(true)
      connect()
    } catch (err) {
      console.error('Camera error:', err)
    }
  }, [connect])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    clearInterval(frameTimerRef.current)
    disconnect()
    setCameraOn(false)
  }, [disconnect])

  // Capture and send frames
  useEffect(() => {
    if (!cameraOn || !isConnected) return

    const capture = () => {
      const video = videoRef.current
      const canvas = captureCanvasRef.current
      if (!video || !canvas || video.readyState < 2) return

      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
      const base64 = dataUrl.split(',')[1]
      sendFrame(base64)
    }

    frameTimerRef.current = setInterval(capture, FRAME_INTERVAL_MS)
    return () => clearInterval(frameTimerRef.current)
  }, [cameraOn, isConnected, sendFrame])

  // Heatmap image from server
  const heatmapSrc = lastFrame?.priority_map_base64
    ? `data:image/png;base64,${lastFrame.priority_map_base64}`
    : null

  const detections = lastFrame?.detections ?? []
  const spqi = lastFrame?.spqi ?? 0
  const latency = lastFrame?.processing_time_ms ?? 0
  const sceneType = lastFrame?.scene_type ?? '—'

  return (
    <div className="space-y-4">
      {/* Controls bar */}
      <div className="flex items-center gap-4 flex-wrap">
        <button
          onClick={cameraOn ? stopCamera : startCamera}
          className={`
            flex items-center gap-2 px-5 py-2.5 rounded-btn font-semibold text-sm transition-all duration-200
            ${cameraOn
              ? 'bg-data-red/15 text-data-red border border-data-red/30 hover:bg-data-red/25'
              : 'bg-accent text-white shadow-glow hover:bg-accent-light'
            }
          `}
        >
          {cameraOn ? <CameraOff size={16} /> : <Camera size={16} />}
          {cameraOn ? 'Stop Camera' : 'Start Camera'}
        </button>

        {/* Live stats */}
        {cameraOn && (
          <div className="flex items-center gap-6 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <Eye size={13} className="text-data-green" />
              <span className="text-text-muted">SPQI</span>
              <span className="text-data-green font-medium">{spqi.toFixed ? spqi.toFixed(2) : spqi}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Zap size={13} className="text-data-amber" />
              <span className="text-text-muted">Latency</span>
              <span className="text-data-amber font-medium">{latency.toFixed ? latency.toFixed(1) : latency}ms</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-text-muted">Scene</span>
              <span className="text-data-blue font-medium">{sceneType}</span>
            </div>
          </div>
        )}
      </div>

      {/* Video grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Raw feed */}
        <div className="space-y-2">
          <p className="text-xs text-text-muted font-mono">📷 Raw Camera Feed</p>
          <div
            className="relative rounded-card overflow-hidden bg-black aspect-video"
            style={{ border: '1px solid rgba(79,70,229,0.2)' }}
          >
            <video
              ref={videoRef}
              muted
              playsInline
              className="w-full h-full object-cover"
            />
            <DetectionOverlay
              detections={detections}
              width={dimensions.width}
              height={dimensions.height}
            />
            {!cameraOn && (
              <div className="absolute inset-0 flex items-center justify-center">
                <CameraOff size={32} className="text-text-muted" />
              </div>
            )}
          </div>
        </div>

        {/* Priority heatmap */}
        <div className="space-y-2">
          <p className="text-xs text-text-muted font-mono">🔥 Priority Heatmap</p>
          <div
            className="relative rounded-card overflow-hidden bg-black aspect-video flex items-center justify-center"
            style={{ border: '1px solid rgba(0,255,135,0.2)' }}
          >
            {heatmapSrc ? (
              <img
                src={heatmapSrc}
                alt="Priority heatmap"
                className="w-full h-full object-cover"
              />
            ) : (
              <p className="text-text-muted text-sm">
                {cameraOn ? 'Awaiting frames…' : 'Start camera to see heatmap'}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Hidden capture canvas */}
      <canvas
        ref={captureCanvasRef}
        width={dimensions.width}
        height={dimensions.height}
        className="hidden"
      />

      {/* Error */}
      {error && (
        <p className="text-xs text-data-red font-mono">WS Error: {error}</p>
      )}
    </div>
  )
}
