/**
 * components/video/VideoPlayer.jsx
 * hls.js-backed player with custom controls.
 * Falls back to native <video> for direct MP4.
 */

import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { Play, Pause, Volume2, VolumeX, Maximize2 } from 'lucide-react'

function formatTime(secs) {
  if (!isFinite(secs)) return '0:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export default function VideoPlayer({ src, poster, className = '' }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)

  useEffect(() => {
    if (!src || !videoRef.current) return
    const video = videoRef.current

    if (src.includes('.m3u8') && Hls.isSupported()) {
      const hls = new Hls()
      hlsRef.current = hls
      hls.loadSource(src)
      hls.attachMedia(video)
    } else {
      video.src = src
    }

    return () => {
      hlsRef.current?.destroy()
      hlsRef.current = null
    }
  }, [src])

  const handleTimeUpdate = () => {
    const video = videoRef.current
    if (!video) return
    setCurrentTime(video.currentTime)
    setProgress(video.duration ? (video.currentTime / video.duration) * 100 : 0)
  }

  const handleLoadedMetadata = () => {
    setDuration(videoRef.current?.duration ?? 0)
  }

  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) { video.play(); setPlaying(true) }
    else { video.pause(); setPlaying(false) }
  }

  const toggleMute = () => {
    const video = videoRef.current
    if (!video) return
    video.muted = !video.muted
    setMuted(video.muted)
  }

  const handleSeek = (e) => {
    const video = videoRef.current
    if (!video) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pct = (e.clientX - rect.left) / rect.width
    video.currentTime = pct * video.duration
  }

  const handleFullscreen = () => {
    videoRef.current?.requestFullscreen?.()
  }

  return (
    <div className={`relative rounded-card overflow-hidden bg-black group ${className}`}>
      <video
        ref={videoRef}
        poster={poster}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={() => setPlaying(false)}
        className="w-full aspect-video object-contain"
        onClick={togglePlay}
      />

      {/* Controls overlay */}
      <div
        className="absolute inset-x-0 bottom-0 p-3 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
        style={{ background: 'linear-gradient(transparent, rgba(0,0,0,0.8))' }}
      >
        {/* Progress bar */}
        <div
          className="w-full h-1 rounded-full cursor-pointer"
          style={{ background: 'rgba(255,255,255,0.2)' }}
          onClick={handleSeek}
        >
          <div
            className="h-full rounded-full bg-accent-light transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Buttons */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={togglePlay} className="text-white hover:text-accent-light transition-colors">
              {playing ? <Pause size={18} /> : <Play size={18} />}
            </button>
            <button onClick={toggleMute} className="text-white hover:text-accent-light transition-colors">
              {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>
            <span className="text-xs font-mono text-white/70">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>
          <button onClick={handleFullscreen} className="text-white hover:text-accent-light transition-colors">
            <Maximize2 size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
