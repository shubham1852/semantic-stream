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

const FPS_TARGET = 10
const FRAME_INTERVAL_MS = 1000 / FPS_TARGET // 100ms (10 fps)

export default function LiveCameraView({ onConnectionChange, onFrameReceived }) {
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

  // Propagate each new server frame to the parent so it can render
  // the latency chart and detection count without touching WS internals.
  useEffect(() => {
    if (lastFrame != null) {
      onFrameReceived?.(lastFrame)
    }
  }, [lastFrame, onFrameReceived])

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

  // Capture and send frames at target 10fps
  useEffect(() => {
    if (!cameraOn || !isConnected) return

    let lastSendTime = 0
    const capture = () => {
      const video = videoRef.current
      const canvas = captureCanvasRef.current
      if (!video || !canvas || video.readyState < 2) return

      const now = Date.now()
      if (now - lastSendTime < FRAME_INTERVAL_MS) return
      lastSendTime = now

      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
      const base64 = dataUrl.split(',')[1]
      sendFrame(base64)
    }

    frameTimerRef.current = setInterval(capture, Math.floor(FRAME_INTERVAL_MS / 2))
    return () => clearInterval(frameTimerRef.current)
  }, [cameraOn, isConnected, sendFrame])

  // Heatmap image from server (handles both JPEG and PNG base64 payloads)
  const heatmapSrc = lastFrame?.priority_map_base64
    ? (lastFrame.priority_map_base64.startsWith('data:')
        ? lastFrame.priority_map_base64
        : `data:image/jpeg;base64,${lastFrame.priority_map_base64}`)
    : null

  const detections = lastFrame?.detections ?? []
  const latency = lastFrame?.processing_time_ms ?? 0
  const sceneType = lastFrame?.scene_type ?? '—'
  const priorityCoverage = lastFrame?.pcs != null
    ? `${Number(lastFrame.pcs).toFixed(1)}%`
    : (lastFrame?.spqi != null && lastFrame.spqi > 0 ? Number(lastFrame.spqi).toFixed(2) : '—')

  // Compute detection count per priority tier
  const tierCounts = detections.reduce((acc, det) => {
    const tier = (det.priority_tier || 'P4').toUpperCase().replace('TIER_', '')
    acc[tier] = (acc[tier] || 0) + 1
    return acc
  }, {})

  const getSceneColor = (st) => {
    const s = (st || '').toUpperCase()
    if (s === 'DIALOGUE') return 'text-green-400'
    if (s === 'ACTION') return 'text-red-400'
    if (s === 'TITLE CARD' || s === 'TEXT_HEAVY') return 'text-cyan-400'
    if (s === 'GENERAL') return 'text-slate-300'
    return 'text-slate-300'
  }

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
          <div className="flex items-center gap-6 text-xs font-mono flex-wrap">
            <div className="flex items-center gap-1.5">
              <Eye size={13} className="text-data-green" />
              <span className="text-text-muted">Priority Coverage</span>
              <span className="text-data-green font-medium">{priorityCoverage}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Zap size={13} className="text-data-amber" />
              <span className="text-text-muted">Latency</span>
              <span className="text-data-amber font-medium">{latency.toFixed ? latency.toFixed(1) : latency}ms</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-text-muted">Scene</span>
              <span className={`font-medium ${getSceneColor(sceneType)}`}>
                {sceneType === 'ambient' ? 'GENERAL' : (sceneType ? sceneType.toUpperCase() : '—')}
              </span>
            </div>

            {/* Tier breakdown — show how many detections per tier */}
            <div className="flex items-center gap-3 pl-3 border-l border-white/10">
              {tierCounts.P1 > 0 && (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-green-400" />
                  <span className="text-green-400 font-semibold">P1×{tierCounts.P1}</span>
                </span>
              )}
              {tierCounts.P2 > 0 && (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-cyan-400" />
                  <span className="text-cyan-400 font-semibold">P2×{tierCounts.P2}</span>
                </span>
              )}
              {tierCounts.P3 > 0 && (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-amber-400" />
                  <span className="text-amber-400 font-semibold">P3×{tierCounts.P3}</span>
                </span>
              )}
              {tierCounts.P4 > 0 && (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-sm bg-orange-400" />
                  <span className="text-orange-400 font-semibold">P4×{tierCounts.P4}</span>
                </span>
              )}
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

          {/* Gradient scale above heatmap */}
          <div className="flex items-center gap-2 mb-2 px-1">
            <span className="text-xs text-slate-500">Low Priority</span>
            <div
              className="flex-1 h-2 rounded-full"
              style={{
                background: 'linear-gradient(to right, #0000ff, #00ffff, #00ff00, #ffff00, #ff0000)',
              }}
            />
            <span className="text-xs text-slate-500">High Priority</span>
          </div>

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

          {/* Heatmap Color Legend below heatmap */}
          <div className="mt-3 flex items-center justify-between px-2">
            <span className="text-xs text-slate-400 font-medium">Priority Legend:</span>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm" style={{ background: 'rgb(255,0,0)' }} />
                <span className="text-xs text-slate-300">P1 Face (QP 18)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm" style={{ background: 'rgb(255,165,0)' }} />
                <span className="text-xs text-slate-300">P2–P4 Objects</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm" style={{ background: 'rgb(0,0,255)' }} />
                <span className="text-xs text-slate-300">P5 Background (QP 42)</span>
              </div>
            </div>
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
