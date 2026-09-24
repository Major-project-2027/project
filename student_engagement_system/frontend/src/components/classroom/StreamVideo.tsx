import { useEffect, useRef, type ReactNode } from 'react'
import { MicOff, MonitorUp, VideoOff } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import { cn } from '@/lib/utils'

/**
 * Attaches a MediaStream to a <video> element via a ref (instead of a DOM id
 * lookup) and keeps it attached across re-renders. `muted` should be true
 * for your own preview (no echo) and false for remote participants you
 * should hear.
 */
export function StreamVideo({
  stream,
  muted,
  mirrored,
  className,
  testId,
}: {
  stream: MediaStream | null
  muted: boolean
  mirrored?: boolean
  className?: string
  testId?: string
}) {
  const ref = useRef<HTMLVideoElement | null>(null)

  useEffect(() => {
    const video = ref.current
    if (!video) return
    if (video.srcObject !== stream) {
      video.srcObject = stream
    }
    if (stream) {
      video.play().catch(() => {
        // Autoplay with sound can be blocked until the user interacts;
        // the next user gesture (any click on the page) retries.
        const retry = () => video.play().catch(() => {})
        window.addEventListener('pointerdown', retry, { once: true })
      })
    }
  }, [stream])

  return (
    <video
      ref={ref}
      data-testid={testId}
      autoPlay
      playsInline
      muted={muted}
      className={cn('h-full w-full object-cover', mirrored && '-scale-x-100', className)}
    />
  )
}

/**
 * A large stage tile: the live video when `videoOn`, otherwise an avatar
 * placeholder (never a frozen/black frame). The <video> stays mounted
 * either way so audio keeps playing while the camera is off.
 */
export function StageTile({
  name,
  label,
  stream,
  videoOn,
  micOn,
  screenSharing,
  muted,
  mirrored,
  testId,
  children,
}: {
  name: string
  label: string
  stream: MediaStream | null
  videoOn: boolean
  micOn: boolean
  screenSharing?: boolean
  muted: boolean
  mirrored?: boolean
  testId?: string
  children?: ReactNode
}) {
  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-2xl bg-gradient-to-br from-focus-900/60 to-[#0f131e]">
      <div className={cn('absolute inset-0', !videoOn && 'invisible')}>
        <StreamVideo
          stream={stream}
          muted={muted}
          mirrored={mirrored && !screenSharing}
          className={screenSharing ? 'object-contain' : undefined}
          testId={testId}
        />
      </div>

      {!videoOn && (
        <div className="flex flex-col items-center gap-3">
          <Avatar name={name} size={84} />
          <span className="flex items-center gap-1.5 rounded-md bg-black/50 px-2.5 py-1 text-xs text-white/80">
            <VideoOff className="h-3.5 w-3.5" />
            Camera off
          </span>
        </div>
      )}

      <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-md bg-black/50 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
        {!micOn && <MicOff className="h-3.5 w-3.5 text-critical-400" aria-label="Microphone muted" />}
        {label}
      </div>

      {screenSharing && (
        <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md bg-focus-500/80 px-2.5 py-1 text-xs font-medium text-white">
          <MonitorUp className="h-3.5 w-3.5" />
          Sharing screen
        </div>
      )}

      {children}
    </div>
  )
}
