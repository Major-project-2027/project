import { MicOff, Mic, Hand, ShieldAlert, AlertTriangle, TrendingDown, CheckCircle2 } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import type { PredictionLabel, StudentLiveState } from '@/types/domain'
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

export function ParticipantsPanel({ students }: { students: StudentLiveState[] }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-4 py-3">
        <p className="text-sm font-semibold text-white">Participants ({students.length})</p>
        <p className="mt-0.5 text-[11px] text-white/40">Sorted by lowest predicted engagement first</p>
      </div>
      <ul className="flex-1 space-y-1 overflow-y-auto p-2">
        {students.map((s, index) => {
          const tone = engagementTone(s.currentEngagement)
          const predictionLabel = s.predictionLabel ?? 'unavailable'
          const PredictionIcon = PREDICTION_ICON[predictionLabel]
          const predictionTone = predictionLabelTone(predictionLabel)
          const highPriority = predictionLabel === 'attention_drop_predicted'

          return (
            <li
              key={s.studentId}
              className={cn(
                'rounded-lg px-2 py-2 hover:bg-white/5',
                highPriority && 'bg-critical-500/10 ring-1 ring-inset ring-critical-500/30',
              )}
            >
              <div className="flex items-center gap-2.5">
                <span className="w-4 shrink-0 text-right text-[11px] text-white/30">{index + 1}.</span>
                <Avatar name={s.studentName} size={30} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white">{s.studentName}</p>
                  <p className="truncate text-[11px] text-white/50">
                    Current: {s.currentEngagement}%
                    {typeof s.predictedEngagement === 'number' && (
                      <> · Predicted: {Math.round(s.predictedEngagement)}%</>
                    )}
                  </p>
                </div>
                {s.handRaised && <Hand className="h-3.5 w-3.5 shrink-0 text-attention-400" />}
                {!s.micOn ? <MicOff className="h-3.5 w-3.5 shrink-0 text-white/40" /> : <Mic className="h-3.5 w-3.5 shrink-0 text-white/40" />}
                {!s.authenticated && <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-critical-400" />}
                <Badge variant={tone} className="shrink-0">{s.currentEngagement}</Badge>
              </div>

              <div className={cn('mt-1 flex items-center gap-1.5 pl-[46px] text-[11px]', PREDICTION_TEXT_CLASS[predictionTone])}>
                {PredictionIcon && <PredictionIcon className="h-3 w-3 shrink-0" />}
                {predictionLabelText(predictionLabel)}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
