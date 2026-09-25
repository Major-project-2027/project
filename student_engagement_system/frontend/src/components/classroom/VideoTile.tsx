import { MicOff, VideoOff, Hand, ShieldAlert } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import { ConfidenceRing } from '@/components/monitoring/ConfidenceRing'
import { StreamVideo } from '@/components/classroom/StreamVideo'
import { cn, engagementTone } from '@/lib/utils'
import type { StudentLiveState } from '@/types/domain'

const TONE_RING = {
  engaged: 'ring-engaged-500/60',
  attention: 'ring-attention-500/60',
  critical: 'ring-critical-500/70',
}

export function VideoTile({
  student,
  stream,
  onSelect,
  selected,
}: {
  student: StudentLiveState
  // The student's live WebRTC stream (video + audio), if connected.
  stream?: MediaStream | null
  onSelect?: () => void
  selected?: boolean
}) {
  const tone = engagementTone(student.currentEngagement)

  return (
    <button
      onClick={onSelect}
      className={cn(
        'group relative aspect-video overflow-hidden rounded-xl bg-[#161b28] text-left ring-2 ring-transparent transition-all',
        selected && TONE_RING[tone],
        student.activeAlert && 'ring-2 ' + TONE_RING.critical,
      )}
    >
      {/* Live stream stays mounted (so the student's audio keeps playing
          when their camera is off); the avatar covers it when off. */}
      <div className={cn('absolute inset-0', !student.cameraOn && 'invisible')}>
        <StreamVideo
          stream={stream ?? null}
          muted={!student.micOn}
          testId={`student-video-${student.studentId}`}
        />
      </div>

      {student.cameraOn ? null : (
        <div className="absolute inset-0 flex items-center justify-center">
          <Avatar
            name={student.studentName}
            size={56}
          />

          <div className="absolute bottom-2 right-2 flex items-center gap-1 rounded-md bg-black/60 px-2 py-1 text-xs text-white">
            <VideoOff className="h-3 w-3" />
            Camera off
          </div>
        </div>
      )}

      {/* Top-left name + authentication */}
      <div className="absolute left-2 top-2 flex items-center gap-1.5 rounded-md bg-black/50 px-2 py-1 text-[11px] font-medium text-white backdrop-blur">
        {!student.authenticated && (
          <ShieldAlert className="h-3 w-3 text-critical-400" />
        )}

        {student.studentName.split(' ')[0]}
      </div>

      {/* Student in frame but face not visible (backend's confirmed state) */}
      {student.cameraOn && (student.noFaceDetected || student.activeAlert === 'no_face_detected') && (
        <div
          className="absolute bottom-2 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-critical-500/85 px-2 py-0.5 text-[11px] font-medium text-white"
          data-testid={`face-not-detected-${student.studentId}`}
        >
          Face not detected
        </div>
      )}

      {/* Top-right alert */}
      {student.activeAlert && (
        <div className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-critical-500 text-white">
          <ShieldAlert className="h-3 w-3" />
        </div>
      )}

      {/* Bottom-left mic / hand */}
      <div className="absolute bottom-2 left-2 flex items-center gap-1">
        {!student.micOn && (
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white">
            <MicOff className="h-3 w-3" />
          </div>
        )}

        {student.handRaised && (
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-attention-500 text-white">
            <Hand className="h-3 w-3" />
          </div>
        )}
      </div>

      {/* Bottom-right engagement ring */}
      <div className="absolute bottom-1.5 right-1.5">
        <ConfidenceRing
          value={student.currentEngagement}
          size={34}
          strokeWidth={3.5}
        />
      </div>
    </button>
  )
}