// FILE: frontend/src/components/video/LiveCameraView.jsx
/**
 * components/video/LiveCameraView.jsx
 * ====================================
 * Webcam capture & WebSocket pipeline component for SemanticStream (Phase 10).
 *
 * Requirements:
 *   - Captures webcam stream at 10fps using setInterval + canvas drawImage + toDataURL('image/jpeg', 0.65).
 *   - Strips base64 prefix and sends { frame: base64strip, bandwidth_factor: props.bandwidthFactor } over WebSocket.
 *   - Parses incoming WebSocket JSON messages and invokes:
 *       props.onAnnotatedFrame(data.annotated_frame)
 *       props.onHeatmapFrame(data.heatmap_frame)
 *       props.onStatsUpdate(data)
 *   - In-flight request gating: prevents frames from queueing up if the server is still processing,
 *     ensuring instantaneous responsiveness and zero buffering lag.
 *   - Headless operation: does NOT render video/canvas inside this component.
 *     All visual canvases and UI elements are rendered in LivePage.jsx.
 *   - Exposes imperative ref with start() and stop() methods.
 */

import React, { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'

const CAPTURE_FPS = 10
const FRAME_INTERVAL_MS = 1000 / CAPTURE_FPS // 100ms
const CAPTURE_WIDTH = 640
const CAPTURE_HEIGHT = 480

const LiveCameraView = forwardRef(function LiveCameraView(props, ref) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const wsRef = useRef(null)
  const streamRef = useRef(null)
  const intervalRef = useRef(null)
  const isRunningRef = useRef(false)
  const isWaitingForResponseRef = useRef(false)
  const lastSendTimeRef = useRef(0)

  // Keep reference to latest props to prevent stale closure inside setInterval
  const propsRef = useRef(props)
  useEffect(() => {
    propsRef.current = props
  }, [props])

  const stop = () => {
    isRunningRef.current = false
    isWaitingForResponseRef.current = false

    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch (err) {
        // ignore close error
      }
      wsRef.current = null
    }

    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((track) => track.stop())
      } catch (err) {
        // ignore track stop error
      }
      streamRef.current = null
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    if (propsRef.current.onConnectionChange) {
      propsRef.current.onConnectionChange(false)
    }
  }

  const start = async () => {
    stop() // Ensure clean state before starting
    isRunningRef.current = true
    isWaitingForResponseRef.current = false

    try {
      // 1. Acquire webcam stream
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: CAPTURE_WIDTH },
          height: { ideal: CAPTURE_HEIGHT },
          frameRate: { ideal: CAPTURE_FPS },
        },
        audio: false,
      })
      streamRef.current = stream

      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => {})
      }

      // 2. Connect WebSocket to /ws/live
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host =
        window.location.port === '5173'
          ? `${window.location.hostname}:8000`
          : window.location.host
      const wsUrl = `${protocol}//${host}/ws/live`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (!isRunningRef.current) return
        isWaitingForResponseRef.current = false
        if (propsRef.current.onConnectionChange) {
          propsRef.current.onConnectionChange(true)
        }
      }

      ws.onmessage = (event) => {
        if (!isRunningRef.current) return
        isWaitingForResponseRef.current = false // Server responded, ready for next frame

        try {
          const data = JSON.parse(event.data)
          if (data.annotated_frame && propsRef.current.onAnnotatedFrame) {
            propsRef.current.onAnnotatedFrame(data.annotated_frame)
          }
          if (data.heatmap_frame && propsRef.current.onHeatmapFrame) {
            propsRef.current.onHeatmapFrame(data.heatmap_frame)
          }
          if (propsRef.current.onStatsUpdate) {
            propsRef.current.onStatsUpdate(data)
          }
        } catch (err) {
          console.error('[LiveCameraView] Error parsing WebSocket message:', err)
        }
      }

      ws.onerror = (err) => {
        isWaitingForResponseRef.current = false
        console.error('[LiveCameraView] WebSocket error:', err)
      }

      ws.onclose = () => {
        isWaitingForResponseRef.current = false
        if (propsRef.current.onConnectionChange) {
          propsRef.current.onConnectionChange(false)
        }
      }

      // 3. Start 10fps frame capture interval with in-flight backpressure protection
      intervalRef.current = setInterval(() => {
        if (!isRunningRef.current) return
        const video = videoRef.current
        const canvas = canvasRef.current
        const activeWs = wsRef.current

        if (!video || !canvas || !activeWs || activeWs.readyState !== WebSocket.OPEN) {
          return
        }

        if (video.videoWidth === 0 || video.videoHeight === 0) {
          return
        }

        // Backpressure guard: if previous frame hasn't returned yet, don't spam the network buffer!
        // Timeout guard: reset if >400ms passes without server response to prevent deadlocks
        const now = Date.now()
        if (isWaitingForResponseRef.current && now - lastSendTimeRef.current < 400) {
          return
        }

        const ctx = canvas.getContext('2d', { alpha: false })
        if (!ctx) return

        canvas.width = CAPTURE_WIDTH
        canvas.height = CAPTURE_HEIGHT
        ctx.drawImage(video, 0, 0, CAPTURE_WIDTH, CAPTURE_HEIGHT)

        const dataUrl = canvas.toDataURL('image/jpeg', 0.65)
        const base64strip = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl

        const bwFactor =
          typeof propsRef.current.bandwidthFactor === 'number'
            ? propsRef.current.bandwidthFactor
            : 1.0

        const payload = JSON.stringify({
          frame: base64strip,
          bandwidth_factor: bwFactor,
        })

        isWaitingForResponseRef.current = true
        lastSendTimeRef.current = now
        activeWs.send(payload)
      }, FRAME_INTERVAL_MS)
    } catch (err) {
      console.error('[LiveCameraView] Failed to start webcam capture:', err)
      stop()
      throw err
    }
  }

  // Expose imperative handle with start() and stop()
  useImperativeHandle(ref, () => ({
    start,
    stop,
    isRunning: () => isRunningRef.current,
  }))

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop()
    }
  }, [])

  // Headless elements: hidden off-screen video and canvas for capturing frames
  return (
    <div style={{ display: 'none' }} aria-hidden="true">
      <video ref={videoRef} playsInline muted autoPlay width={CAPTURE_WIDTH} height={CAPTURE_HEIGHT} />
      <canvas ref={canvasRef} width={CAPTURE_WIDTH} height={CAPTURE_HEIGHT} />
    </div>
  )
})

export default LiveCameraView
