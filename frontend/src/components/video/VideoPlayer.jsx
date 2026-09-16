/**
 * components/video/VideoPlayer.jsx
 * Robust player supporting both HLS adaptive streams (.m3u8) and direct MP4 playback.
 * Features a glowing center play button, custom controls overlay, seek bar, and error recovery.
 */

import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { Play, Pause, Volume2, VolumeX, Maximize2, AlertCircle, RefreshCw } from 'lucide-react'
import Spinner from '../ui/Spinner'

function formatTime(secs) {
  if (!isFinite(secs) || secs == null) return '0:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export default function VideoPlayer({ src, poster, className = '', _title = 'Processed Video' }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [buffering, setBuffering] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [activeSrc, setActiveSrc] = useState(src)

  useEffect(() => {
    setActiveSrc(src)
    setLoadError(null)
  }, [src])

  useEffect(() => {
    if (!activeSrc || !videoRef.current) return
    const video = videoRef.current

    setLoadError(null)

    if (activeSrc.includes('.m3u8') && Hls.isSupported()) {
      const hls = new Hls({
        maxBufferLength: 30,
        enableWorker: true,
      })
      hlsRef.current = hls
      hls.loadSource(activeSrc)
      hls.attachMedia(video)

      hls.on(Hls.Events.ERROR, (event, data) => {
        // If HLS manifest load or parse fails, switch to direct MP4 processed/raw fallback
        if (data.fatal || data.details === 'manifestParsingError') {
          hls.destroy()
          hlsRef.current = null
          const fallbackSrc = activeSrc.includes('/playlist.m3u8')
            ? activeSrc.replace('/playlist.m3u8', '/processed')
            : activeSrc.replace(/\.m3u8$/, '')
          setActiveSrc(fallbackSrc)
        }
      })
    } else if (activeSrc.includes('.m3u8') && video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari native HLS
      video.src = activeSrc
    } else {
      // Direct MP4 playback
      video.src = activeSrc
      video.load()
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy()
        hlsRef.current = null
      }
    }
  }, [activeSrc])

  const handleTimeUpdate = () => {
    const video = videoRef.current
    if (!video) return
    setCurrentTime(video.currentTime)
    setProgress(video.duration ? (video.currentTime / video.duration) * 100 : 0)
  }

  const handleLoadedMetadata = () => {
    setDuration(videoRef.current?.duration ?? 0)
    setBuffering(false)
    setLoadError(null)
  }

  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return
    if (video.paused) {
      video.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
    } else {
      video.pause()
      setPlaying(false)
    }
  }

  const toggleMute = (e) => {
    e.stopPropagation()
    const video = videoRef.current
    if (!video) return
    video.muted = !video.muted
    setMuted(video.muted)
  }

  const handleSeek = (e) => {
    e.stopPropagation()
    const video = videoRef.current
    if (!video) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    video.currentTime = pct * (video.duration || 0)
  }

  const handleFullscreen = (e) => {
    e.stopPropagation()
    videoRef.current?.requestFullscreen?.()
  }

  const handleRetry = () => {
    setLoadError(null)
    if (videoRef.current) {
      videoRef.current.load()
    }
  }

  return (
    <div className={`relative rounded-card overflow-hidden bg-black group border border-border-subtle shadow-2xl select-none ${className}`}>
      <video
        ref={videoRef}
        poster={poster}
        preload="metadata"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onWaiting={() => setBuffering(true)}
        onPlaying={() => { setBuffering(false); setPlaying(true) }}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onError={() => {
          // If processed failed, try raw fallback
          if (activeSrc && activeSrc.includes('/processed')) {
            setActiveSrc(activeSrc.replace('/processed', '/raw'))
          } else {
            setLoadError('Unable to load video stream')
            setBuffering(false)
          }
        }}
        className="w-full aspect-video object-contain cursor-pointer"
        onClick={togglePlay}
        playsInline
      />

      {/* Buffering Indicator */}
      {buffering && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 pointer-events-none">
          <Spinner size={36} color="#00FF87" />
        </div>
      )}

      {/* Prominent Center Play Button Overlay (when paused and ready) */}
      {!playing && !buffering && !loadError && (
        <div
          onClick={togglePlay}
          className="absolute inset-0 flex items-center justify-center bg-black/25 cursor-pointer transition-all duration-200 hover:bg-black/35"
        >
          <button
            type="button"
            className="w-16 h-16 rounded-full flex items-center justify-center bg-accent/90 hover:bg-accent text-white shadow-glow transition-transform duration-200 hover:scale-110 active:scale-95"
            aria-label="Play video"
          >
            <Play size={28} className="translate-x-0.5 text-black fill-black" />
          </button>
        </div>
      )}

      {/* Error Overlay */}
      {loadError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80 p-4 text-center">
          <AlertCircle size={32} className="text-data-red" />
          <p className="text-sm font-medium text-text-primary">{loadError}</p>
          <button
            onClick={handleRetry}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-btn bg-surface-2 hover:bg-surface-3 text-text-primary border border-border transition-colors"
          >
            <RefreshCw size={12} />
            Retry Playback
          </button>
        </div>
      )}

      {/* Bottom Controls Overlay */}
      <div
        className={`absolute inset-x-0 bottom-0 p-3.5 flex flex-col gap-2.5 transition-opacity duration-200 ${
          playing ? 'opacity-0 group-hover:opacity-100' : 'opacity-100'
        }`}
        style={{ background: 'linear-gradient(transparent, rgba(10,14,26,0.92))' }}
      >
        {/* Progress bar */}
        <div
          className="w-full h-1.5 rounded-full cursor-pointer bg-white/20 hover:h-2 transition-all relative"
          onClick={handleSeek}
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-accent-light to-accent transition-all duration-75 relative"
            style={{ width: `${progress}%` }}
          >
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white shadow opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>

        {/* Action Buttons & Time */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={togglePlay}
              className="text-white hover:text-accent-light transition-colors p-1"
              aria-label={playing ? 'Pause' : 'Play'}
            >
              {playing ? <Pause size={18} /> : <Play size={18} className="fill-current" />}
            </button>
            <button
              onClick={toggleMute}
              className="text-white hover:text-accent-light transition-colors p-1"
              aria-label={muted ? 'Unmute' : 'Mute'}
            >
              {muted ? <VolumeX size={17} /> : <Volume2 size={17} />}
            </button>
            <span className="text-xs font-mono text-white/80 font-medium">
              {formatTime(currentTime)} <span className="text-white/40">/</span> {formatTime(duration)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleFullscreen}
              className="text-white hover:text-accent-light transition-colors p-1"
              aria-label="Fullscreen"
            >
              <Maximize2 size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
