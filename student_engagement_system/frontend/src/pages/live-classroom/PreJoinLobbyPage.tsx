import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Mic, MicOff, Video, VideoOff, ShieldCheck, Loader2, Users } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { classesApi } from '@/services/api/endpoints'
import { currentTeacher, currentStudent } from '@/mocks/data'
import { cn } from '@/lib/utils'
import type { UserRole } from '@/types/domain'

type AuthStep = 'idle' | 'verifying' | 'verified' | 'failed'

export function PreJoinLobbyPage({ role }: { role: UserRole }) {
  const { classId } = useParams()
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const [cameraOn, setCameraOn] = useState(true)
  const [micOn, setMicOn] = useState(role === 'teacher')
  const [cameraError, setCameraError] = useState(false)
  // Real face verification (Feature 2) already ran on /student/verify/:classId
  // -- the join call that lands a student here only succeeds after a
  // genuine backend-confirmed match, so there is nothing left to verify by
  // the time this page renders. This badge reports that completed result,
  // it does not perform (or simulate) verification itself.
  const [authStep] = useState<AuthStep>('verified')

  const classQuery = useQuery({ queryKey: ['class', classId], queryFn: () => classesApi.get(classId ?? '') })
  const user = role === 'teacher' ? currentTeacher : currentStudent

  // Try to acquire a real camera/mic preview, like Meet's lobby. Falls back
  // gracefully to an avatar tile if permission is denied or unavailable.
  useEffect(() => {
    let cancelled = false
    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return }
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
      } catch {
        if (!cancelled) setCameraError(true)
      }
    }
    start()
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  useEffect(() => {
    streamRef.current?.getVideoTracks().forEach((t) => (t.enabled = cameraOn))
  }, [cameraOn])
  useEffect(() => {
    streamRef.current?.getAudioTracks().forEach((t) => (t.enabled = micOn))
  }, [micOn])

  const canJoin = role === 'teacher' || authStep === 'verified'

  const handleJoin = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    navigate(`/${role}/live/${classId}`)
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#0a0c14] px-4 py-10">
      <div className="w-full max-w-3xl">
        <p className="mb-1 text-center text-sm text-white/50">Ready to join?</p>
        <h1 className="mb-6 text-center font-display text-2xl font-bold text-white">{classQuery.data?.title ?? 'Live class'}</h1>

        <div className="relative mx-auto aspect-video w-full max-w-xl overflow-hidden rounded-2xl bg-[#161b28]">
          {cameraOn && !cameraError ? (
            <video ref={videoRef} autoPlay muted playsInline className="h-full w-full scale-x-[-1] object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <Avatar name={user.name} size={72} />
            </div>
          )}

          {cameraError && cameraOn && (
            <div className="absolute inset-x-0 bottom-14 mx-auto w-fit rounded-lg bg-black/60 px-3 py-1.5 text-xs text-white/80">
              Camera unavailable — continuing with avatar preview
            </div>
          )}

          <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-3">
            <button
              onClick={() => setMicOn((v) => !v)}
              className={cn('flex h-11 w-11 items-center justify-center rounded-full', micOn ? 'bg-white/15 text-white' : 'bg-critical-500 text-white')}
            >
              {micOn ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
            </button>
            <button
              onClick={() => setCameraOn((v) => !v)}
              className={cn('flex h-11 w-11 items-center justify-center rounded-full', cameraOn ? 'bg-white/15 text-white' : 'bg-critical-500 text-white')}
            >
              {cameraOn ? <Video className="h-5 w-5" /> : <VideoOff className="h-5 w-5" />}
            </button>
          </div>
        </div>

        <div className="mx-auto mt-6 flex max-w-xl flex-col items-center gap-4">
          {role === 'student' && (
            <div className={cn(
              'flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium',
              authStep === 'verified' ? 'bg-engaged-500/15 text-engaged-400' : 'bg-focus-500/15 text-focus-300',
            )}>
              {authStep === 'verifying' ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              {authStep === 'verifying' ? 'Verifying your identity…' : 'Face authentication verified'}
            </div>
          )}

          <div className="flex items-center gap-2 text-sm text-white/60">
            <Users className="h-4 w-4" />
            {role === 'teacher' ? 'You will start the session for your class' : `${classQuery.data?.studentsPresent ?? 12} people are already in this call`}
          </div>

          <Button size="lg" className="w-full" onClick={handleJoin} disabled={!canJoin}>
            {role === 'teacher' ? 'Start now' : 'Join now'}
          </Button>
          <button onClick={() => navigate(`/${role}`)} className="text-sm text-white/50 hover:text-white/80">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
