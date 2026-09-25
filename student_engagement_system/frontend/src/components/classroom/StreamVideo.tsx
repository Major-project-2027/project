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
  const mutedRef = useRef(muted)
  mutedRef.current = muted

  useEffect(() => {
    const video = ref.current
    if (!video) return
    if (video.srcObject !== stream) {
      video.srcObject = stream
    }
    if (!stream) return

    let disposed = false

    const play = () => {
      if (disposed || !video.paused) return
      video.play().catch(() => {
        if (disposed) return
        // Autoplay WITH SOUND can be blocked until the user interacts.
        // Never leave the tile black because of that: play muted now (the
        // video shows), and restore the sound on the next user gesture.
        video.muted = true
        video.play().catch(() => {})
        const restore = () => {
          if (disposed) return
          video.muted = mutedRef.current
          video.play().catch(() => {})
        }
        window.addEventListener('pointerdown', restore, { once: true })
        window.addEventListener('keydown', restore, { once: true })
      })
    }

    // A remote track that was paused (camera turned off -> replaceTrack
    // null, or not yet connected) fires 'unmute' when frames resume, and
    // tracks can be added to the stream after it was attached. Make sure
    // the element is playing again in both cases.
    const tracks = new Set<MediaStreamTrack>()
    const watch = (track: MediaStreamTrack) => {
      if (tracks.has(track)) return
      tracks.add(track)
      track.addEventListener('unmute', play)
    }
    const onAddTrack = (event: MediaStreamTrackEvent) => {
      watch(event.track)
      play()
    }
    stream.getTracks().forEach(watch)
    stream.addEventListener('addtrack', onAddTrack)

    play()

    return () => {
      disposed = true
      tracks.forEach((track) => track.removeEventListener('unmute', play))
      stream.removeEventListener('addtrack', onAddTrack)
    }
  }, [stream])

  // Keep the element's muted state in sync (React only sets it reliably
  // as a property, and the autoplay fallback above may have forced it).
  useEffect(() => {
    const video = ref.current
    if (video && video.muted !== muted) {
      video.muted = muted
      if (!muted && video.srcObject) {
        video.play().catch(() => {
          video.muted = true
          video.play().catch(() => {})
        })
      }
    }
  }, [muted])

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
