import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, ScanFace, XCircle } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { faceApi } from '@/services/api/endpoints'

// Five poses is enough coverage for reliable later matching (a live
// verification frame is rarely a perfect head-on match) without asking
// for exaggerated head movements -- each instruction is a small turn, not
// a dramatic one.
const POSES = [
  { key: 'straight', instruction: 'Look straight at the camera' },
  { key: 'left', instruction: 'Turn slightly left' },
  { key: 'right', instruction: 'Turn slightly right' },
  { key: 'up', instruction: 'Look slightly up' },
  { key: 'down', instruction: 'Look slightly down' },
] as const

type CaptureStatus = 'idle' | 'capturing' | 'error'

export function FaceRegistrationPage() {
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const [cameraError, setCameraError] = useState<string | null>(null)
  const [poseIndex, setPoseIndex] = useState(0)
  const [embeddings, setEmbeddings] = useState<number[][]>([])
  const [status, setStatus] = useState<CaptureStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const allCaptured = poseIndex >= POSES.length

  useEffect(() => {
    let cancelled = false

    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true })

        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }

        streamRef.current = stream

        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
      } catch {
        if (!cancelled) {
          setCameraError(
            'Camera access is required to register your face. Please allow camera access and reload this page.',
          )
        }
      }
    }

    start()

    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const captureCurrentFrame = (): string | null => {
    const video = videoRef.current

    if (!video || video.readyState < 2) {
      return null
    }

    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas')
    }

    const canvas = canvasRef.current
    canvas.width = 480
    canvas.height = 360

    const context = canvas.getContext('2d')

    if (!context) {
      return null
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height)

    return canvas.toDataURL('image/jpeg', 0.85)
  }

  const handleCapture = async () => {
    setError(null)
    setStatus('capturing')

    const frame = captureCurrentFrame()

    if (!frame) {
      setStatus('error')
      setError('Camera is not ready yet. Please wait a moment and try again.')
      return
    }

    try {
      const embedding = await faceApi.validateSample(frame)

      setEmbeddings((current) => [...current, embedding])
      setPoseIndex((current) => current + 1)
      setStatus('idle')
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'No clear face detected. Please try again.')
    }
  }

  const handleComplete = async () => {
    setSubmitting(true)
    setSubmitError(null)

    try {
      await faceApi.register(embeddings)
      streamRef.current?.getTracks().forEach((t) => t.stop())
      setDone(true)
      setTimeout(() => navigate('/student'), 1800)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Unable to save face registration.')
    } finally {
      setSubmitting(false)
    }
  }

  const currentPose = POSES[poseIndex]

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#0a0c14] px-4 py-10">
      <div className="w-full max-w-lg">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-focus-500/15">
            <ScanFace className="h-6 w-6 text-focus-400" />
          </div>
          <h1 className="font-display text-2xl font-bold text-white">Register your face</h1>
          <p className="mt-1 text-sm text-white/50">
            This lets us verify it&apos;s really you before joining a live class.
          </p>
        </div>

        <div className="relative mx-auto aspect-video w-full overflow-hidden rounded-2xl bg-[#161b28]">
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="h-full w-full scale-x-[-1] object-cover"
          />

          {cameraError && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/70 px-6 text-center text-sm text-white/80">
              {cameraError}
            </div>
          )}
        </div>

        {done ? (
          <div className="mt-6 flex flex-col items-center gap-2 rounded-xl bg-engaged-500/10 px-4 py-4 text-center">
            <CheckCircle2 className="h-6 w-6 text-engaged-400" />
            <p className="text-sm font-medium text-engaged-400">
              Face registered successfully. Taking you to your dashboard…
            </p>
          </div>
        ) : allCaptured ? (
          <div className="mt-6 flex flex-col items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-engaged-400">
              <CheckCircle2 className="h-4 w-4" />
              All {POSES.length} samples captured
            </div>

            {submitError && (
              <p className="text-sm text-critical-400">{submitError}</p>
            )}

            <Button size="lg" className="w-full" onClick={handleComplete} loading={submitting}>
              Complete registration
            </Button>
          </div>
        ) : (
          <div className="mt-6 flex flex-col items-center gap-4">
            <p className="text-center text-sm text-white/50">
              Step {poseIndex + 1} of {POSES.length}
            </p>

            <p className="text-center text-lg font-medium text-white">
              {currentPose.instruction}
            </p>

            {status === 'error' && error && (
              <div className="flex items-center gap-2 rounded-lg bg-critical-500/10 px-3 py-2 text-sm text-critical-400">
                <XCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}

            <Button
              size="lg"
              className="w-full"
              onClick={handleCapture}
              loading={status === 'capturing'}
              disabled={Boolean(cameraError)}
            >
              Capture
            </Button>

            <div className="flex items-center gap-1.5">
              {POSES.map((pose, index) => (
                <span
                  key={pose.key}
                  className={
                    index < poseIndex
                      ? 'h-1.5 w-6 rounded-full bg-engaged-500'
                      : index === poseIndex
                        ? 'h-1.5 w-6 rounded-full bg-focus-500'
                        : 'h-1.5 w-6 rounded-full bg-white/15'
                  }
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
