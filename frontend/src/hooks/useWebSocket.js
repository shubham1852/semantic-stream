/**
 * hooks/useWebSocket.js
 * Manages the /ws/live WebSocket connection for real-time camera frame analysis.
 *
 * Protocol:
 *   Send:    { frame_base64: "<JPEG base64>" }
 *   Receive: { priority_map_base64, detections, spqi, confidence,
 *              scene_type, current_qp_assignments, processing_time_ms }
 */

import { useCallback, useEffect, useRef, useState } from 'react'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/live`

export function useWebSocket() {
  const wsRef = useRef(null)
  const [isConnected, setIsConnected] = useState(false)
  const [lastFrame, setLastFrame] = useState(null) // Latest parsed server response
  const [error, setError] = useState(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.error) {
          setError(data.error)
        } else {
          setLastFrame(data)
        }
      } catch {
        // ignore malformed frames
      }
    }

    ws.onerror = () => {
      setError('WebSocket connection error')
      setIsConnected(false)
    }

    ws.onclose = () => {
      setIsConnected(false)
    }
  }, [])

  const disconnect = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
    setIsConnected(false)
    setLastFrame(null)
  }, [])

  const sendFrame = useCallback((frameBase64) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ frame_base64: frameBase64 }))
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => () => wsRef.current?.close(), [])

  return { isConnected, lastFrame, error, connect, disconnect, sendFrame }
}
