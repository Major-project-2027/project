import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, Loader2, ShieldCheck, ShieldX } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { faceApi, classesApi } from '@/services/api/endpoints'

type Phase = 'verifying' | 'failed' | 'joining' | 'no_registration'

/**
 * Face-verification gate a student must pass before joining a live class
 * (Feature 2). This runs BEFORE the join endpoint is ever called -- a
 * genuine match here is what lets /join-live-class succeed at all; the
 * backend independently enforces this (see EnrollmentService), so this
 * page cannot be skipped by, say, navigating straight to the lobby URL
 * with no prior verification -- the join call it depends on would just
 * be rejected server-side.
 */
export function FaceVerificationPage() {
  const { classId } = useParams()
  const navigate = useNavigate()

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const [cameraError, setCameraError] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>('verifying')
  const [message, setMessage] = useState<string | null>(null)
  const [attempts, setAttempts] = useState(0)

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
          setCameraError('Camera access is required to verify your identity.')
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

  const runVerification = async () => {
    if (!classId) {
      return
    }

    setPhase('verifying')
    setMessage(null)

    const frame = captureCurrentFrame()

    if (!frame) {
      setPhase('failed')
      setMessage('Camera is not ready yet. Please wait a moment and try again.')
      return
    }

    try {
      const result = await faceApi.verifyLive(frame, classId)

      setAttempts((count) => count + 1)

      if (!result.matched) {
        setPhase(result.reason === 'not_registered' ? 'no_registration' : 'failed')
        setMessage(result.message)
        return
      }

      // Matched -- now actually join. The backend requires and consumes
      // the verification this call just produced, so this can't succeed
      // without the match above having genuinely happened server-side.
      setPhase('joining')

      await classesApi.joinLive(classId)

      streamRef.current?.getTracks().forEach((t) => t.stop())
      navigate(`/student/lobby/${classId}`)
    } catch (err) {
      setPhase('failed')
      setMessage(err instanceof Error ? err.message : 'Unable to verify identity. Please try again.')
    }
  }

  // Auto-run the first verification attempt once the camera is live.
  useEffect(() => {
    if (cameraError) {
      return
    }

    const timeout = setTimeout(() => {
      runVerification()
    }, 800)

    return () => clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraError])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#0a0c14] px-4 py-10">
      <div className="w-full max-w-lg">
        <p className="mb-1 text-center text-sm text-white/50">Before you join</p>
        <h1 className="mb-6 text-center font-display text-2xl font-bold text-white">
          Face verification
        </h1>

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

        <div className="mx-auto mt-6 flex max-w-xl flex-col items-center gap-4">
          {phase === 'verifying' && (
            <div className="flex items-center gap-2 rounded-full bg-focus-500/15 px-4 py-2 text-sm font-medium text-focus-300">
              <Loader2 className="h-4 w-4 animate-spin" />
              Verifying your identity…
            </div>
          )}

          {phase === 'joining' && (
            <div className="flex items-center gap-2 rounded-full bg-engaged-500/15 px-4 py-2 text-sm font-medium text-engaged-400">
              <ShieldCheck className="h-4 w-4" />
              Identity verified. Joining class…
            </div>
          )}

          {phase === 'failed' && (
            <div className="flex w-full flex-col items-center gap-3">
              <div className="flex items-center gap-2 rounded-full bg-critical-500/15 px-4 py-2 text-sm font-medium text-critical-400">
                <ShieldX className="h-4 w-4" />
                {message ?? 'Student not authenticated. Face verification failed.'}
              </div>

              <Button size="lg" className="w-full" onClick={runVerification}>
                Try again
              </Button>

              {attempts >= 3 && (
                <p className="text-center text-xs text-white/40">
                  Still not matching? Make sure you&apos;re well-lit and facing the camera directly.
                </p>
              )}
            </div>
          )}

          {phase === 'no_registration' && (
            <div className="flex w-full flex-col items-center gap-3">
              <div className="flex items-center gap-2 rounded-full bg-attention-500/15 px-4 py-2 text-sm font-medium text-attention-400">
                <AlertTriangle className="h-4 w-4" />
                {message ?? 'Face registration required.'}
              </div>
            </div>
          )}

          <button
            onClick={() => {
              streamRef.current?.getTracks().forEach((t) => t.stop())
              navigate('/student')
            }}
            className="text-sm text-white/50 hover:text-white/80"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
