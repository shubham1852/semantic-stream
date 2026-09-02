/**
 * components/video/VideoUploader.jsx
 * Drag-and-drop video upload zone with progress tracking.
 */

import { useCallback, useRef, useState } from 'react'
import { Upload, FileVideo, X, CheckCircle } from 'lucide-react'
import { uploadVideo } from '../../api/videos'
import useAppStore from '../../store/useAppStore'
import ProgressBar from '../ui/ProgressBar'
import Button from '../ui/Button'

const ACCEPTED_TYPES = ['video/mp4', 'video/quicktime', 'video/x-msvideo']
const MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024 // 2 GB

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

export default function VideoUploader({ onUploadComplete }) {
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  const upload = useAppStore((s) => s.upload)
  const setUploadFile = useAppStore((s) => s.setUploadFile)
  const setUploadProgress = useAppStore((s) => s.setUploadProgress)
  const setUploadDone = useAppStore((s) => s.setUploadDone)
  const setUploadError = useAppStore((s) => s.setUploadError)
  const resetUpload = useAppStore((s) => s.resetUpload)
  const addToast = useAppStore((s) => s.addToast)

  const handleFile = useCallback(async (file) => {
    if (!file) return

    // Validate type
    if (!ACCEPTED_TYPES.includes(file.type)) {
      addToast({ type: 'error', title: 'Invalid format', message: 'Accepted: MP4, MOV, AVI' })
      return
    }
    if (file.size > MAX_SIZE_BYTES) {
      addToast({ type: 'error', title: 'File too large', message: 'Maximum file size is 2 GB' })
      return
    }

    setUploadFile(file)

    try {
      const data = await uploadVideo(file, setUploadProgress)
      setUploadDone(data.video_id, data)
      addToast({ type: 'success', title: 'Upload complete', message: file.name })
      onUploadComplete?.(data.video_id, data)
    } catch (err) {
      setUploadError(err.message)
      addToast({ type: 'error', title: 'Upload failed', message: err.message })
    }
  }, [setUploadFile, setUploadProgress, setUploadDone, setUploadError, addToast, onUploadComplete])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }, [handleFile])

  const onInputChange = (e) => {
    handleFile(e.target.files[0])
    e.target.value = ''
  }

  const isUploading = upload.status === 'uploading'
  const isDone = upload.status === 'done'

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !isUploading && !isDone && fileInputRef.current?.click()}
        className={`
          relative flex flex-col items-center justify-center gap-4
          border-2 border-dashed rounded-card p-10 cursor-pointer
          transition-all duration-200
          ${dragOver
            ? 'border-accent bg-accent/10 shadow-glow'
            : isDone
              ? 'border-data-green/40 bg-data-green/5'
              : 'border-border-subtle hover:border-accent/50 hover:bg-accent/5'
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/x-msvideo,.mp4,.mov,.avi"
          onChange={onInputChange}
          className="hidden"
          id="video-upload-input"
        />

        {isDone ? (
          <>
            <CheckCircle size={40} className="text-data-green" />
            <div className="text-center">
              <p className="font-semibold text-text-primary">{upload.file?.name}</p>
              <p className="text-sm text-text-muted mt-1">
                {formatBytes(upload.file?.size ?? 0)} · Upload complete
              </p>
              <p className="text-xs text-data-green font-mono mt-1">
                video_id: {upload.videoId}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              icon={X}
              onClick={(e) => { e.stopPropagation(); resetUpload() }}
            >
              Remove
            </Button>
          </>
        ) : upload.file ? (
          <>
            <FileVideo size={40} className="text-accent-light" />
            <div className="text-center">
              <p className="font-semibold text-text-primary">{upload.file.name}</p>
              <p className="text-sm text-text-muted">{formatBytes(upload.file.size)}</p>
            </div>
            {isUploading && (
              <div className="w-full max-w-xs">
                <ProgressBar value={upload.progress} label="Uploading…" />
              </div>
            )}
          </>
        ) : (
          <>
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center"
              style={{ background: 'rgba(79,70,229,0.12)', border: '1px solid rgba(79,70,229,0.25)' }}
            >
              <Upload size={28} className="text-accent-light" />
            </div>
            <div className="text-center">
              <p className="font-semibold text-text-primary">
                {dragOver ? 'Drop your video here' : 'Drag & drop or click to browse'}
              </p>
              <p className="text-sm text-text-muted mt-1">MP4, MOV, AVI · Max 2 GB</p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
