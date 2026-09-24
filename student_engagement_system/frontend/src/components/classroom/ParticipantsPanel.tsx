import { MicOff, Mic, Hand, ShieldAlert, AlertTriangle, TrendingDown, CheckCircle2, Video, VideoOff, MonitorUp } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import type { PredictionLabel, StudentLiveState } from '@/types/domain'
import type { RoomParticipant } from '@/lib/classroomSocket'
import { engagementTone, predictionLabelText, predictionLabelTone, cn } from '@/lib/utils'

const PREDICTION_ICON: Record<PredictionLabel, typeof CheckCircle2 | null> = {
  stable: CheckCircle2,
  attention_may_decrease: TrendingDown,
  attention_drop_predicted: AlertTriangle,
  unavailable: null,
}

const PREDICTION_TEXT_CLASS: Record<'engaged' | 'attention' | 'critical' | 'neutral', string> = {
  engaged: 'text-engaged-400',
  attention: 'text-attention-400',
  critical: 'text-critical-400',
  neutral: 'text-white/40',
}

function statusText(p: RoomParticipant) {
  if (p.media.hand) return 'Hand raised'
  if (!p.media.camera && !p.media.mic) return 'Camera off · Muted'
  if (!p.media.camera) return 'Camera off'
  if (!p.media.mic) return 'Muted'
  return 'Connected'
}

/**
 * Who is actually connected to this class right now (live presence from
 * the classroom WebSocket), with their camera / microphone state. For the
 * teacher, each student row also carries that student's live AI data;
 * `students` (already sorted by the caller) decides the order.
 */
export function ParticipantsPanel({
  participants,
  selfKey,
  students,
}: {
  participants: RoomParticipant[]
  selfKey: string | null
  students?: StudentLiveState[]
}) {
  const aiById = new Map((students ?? []).map((s) => [s.studentId, s]))
  const order = new Map((students ?? []).map((s, i) => [s.studentId, i]))

  const teacherRows = participants.filter((p) => p.role === 'teacher')
  const studentRows = participants
    .filter((p) => p.role === 'student')
    .sort((a, b) => (order.get(a.userId) ?? 1e9) - (order.get(b.userId) ?? 1e9) || a.name.localeCompare(b.name))

  const row = (p: RoomParticipant) => {
    const ai = p.role === 'student' ? aiById.get(p.userId) : undefined
    const predictionLabel = ai?.predictionLabel ?? 'unavailable'
    const PredictionIcon = PREDICTION_ICON[predictionLabel]
    const highPriority = predictionLabel === 'attention_drop_predicted'

    return (
      <li
        key={p.key}
        data-testid={`participant-${p.key}`}
        className={cn(
          'rounded-lg px-2 py-2 hover:bg-white/5',
          highPriority && 'bg-critical-500/10 ring-1 ring-inset ring-critical-500/30',
        )}
      >
        <div className="flex items-center gap-2.5">
          <span className="relative">
            <Avatar name={p.name} size={30} />
            <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-engaged-500 ring-2 ring-[#0f131e]" title="Connected" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">
              {p.name}
              {p.key === selfKey && <span className="text-white/40"> (you)</span>}
              {p.role === 'teacher' && (
                <span className="ml-1 rounded bg-focus-500/30 px-1 text-[10px] text-focus-200">Teacher</span>
              )}
            </p>
            <p className="truncate text-[11px] text-white/50">
              {p.media.screen ? 'Sharing screen' : statusText(p)}
              {ai && <> · {ai.currentEngagement}% engaged</>}
            </p>
          </div>
          {p.media.hand && <Hand className="h-3.5 w-3.5 shrink-0 text-attention-400" aria-label="Hand raised" />}
          {p.media.screen && <MonitorUp className="h-3.5 w-3.5 shrink-0 text-focus-300" aria-label="Sharing screen" />}
          {p.media.camera ? (
            <Video className="h-3.5 w-3.5 shrink-0 text-white/40" aria-label="Camera on" />
          ) : (
            <VideoOff className="h-3.5 w-3.5 shrink-0 text-white/40" aria-label="Camera off" />
          )}
          {p.media.mic ? (
            <Mic className="h-3.5 w-3.5 shrink-0 text-white/40" aria-label="Microphone on" />
          ) : (
            <MicOff className="h-3.5 w-3.5 shrink-0 text-critical-400/80" aria-label="Muted" />
          )}
          {ai && !ai.authenticated && <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-critical-400" />}
          {ai && <Badge variant={engagementTone(ai.currentEngagement)} className="shrink-0">{ai.currentEngagement}</Badge>}
        </div>

        {ai && (
          <div className={cn('mt-1 flex items-center gap-1.5 pl-[42px] text-[11px]', PREDICTION_TEXT_CLASS[predictionLabelTone(predictionLabel)])}>
            {PredictionIcon && <PredictionIcon className="h-3 w-3 shrink-0" />}
            {predictionLabelText(predictionLabel)}
          </div>
        )}
      </li>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-4 py-3">
        <p className="text-sm font-semibold text-white" data-testid="participants-heading">
          Participants ({studentRows.length} {studentRows.length === 1 ? 'student' : 'students'})
        </p>
        {students && <p className="mt-0.5 text-[11px] text-white/40">Students sorted by lowest predicted engagement first</p>}
      </div>
      <ul className="flex-1 space-y-1 overflow-y-auto p-2">
        {teacherRows.map(row)}
        {studentRows.length === 0 ? (
          <li className="px-2 py-6 text-center text-xs text-white/40">No students connected yet</li>
        ) : (
          studentRows.map(row)
        )}
      </ul>
    </div>
  )
}
