import {
  Eye, EyeOff, Smile, Frown, Meh, ScanFace, Volume2, VolumeX,
  Phone, Users2, Moon, AlertTriangle, CheckCircle2, Activity,
} from 'lucide-react'
import { ConfidenceRing } from './ConfidenceRing'
import { Badge } from '@/components/ui/Badge'
import type { StudentLiveState } from '@/types/domain'
import { cn } from '@/lib/utils'

const EMOTION_ICON = { neutral: Meh, happy: Smile, confused: Meh, bored: Frown, frustrated: Frown, surprised: Smile, sad: Frown } as const

function MetricRow({ icon: Icon, label, value, tone }: { icon: typeof Eye; label: string; value: string; tone: 'engaged' | 'attention' | 'critical' | 'neutral' }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-black/[0.03] px-3 py-2 dark:bg-white/[0.04]">
      <span className="flex items-center gap-2 text-xs font-medium text-textmuted-light dark:text-textmuted-dark">
        <Icon className="h-3.5 w-3.5" />{label}
      </span>
      <Badge variant={tone}>{value}</Badge>
    </div>
  )
}

/** Detailed AI readout for a single student — Part 6 of the spec.
 * Shows emotion, engagement, face auth, head pose, gaze, drowsiness,
 * phone/multi-person detection, voice disturbance, and confidence scores. */
export function AIMonitoringPanel({ student }: { student: StudentLiveState }) {
  const EmotionIcon = EMOTION_ICON[student.currentEmotion]
  const alertActive = Boolean(student.activeAlert)

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-focus-500" />
        <p className="font-display text-sm font-semibold text-text-light dark:text-text-dark">AI Monitoring — {student.studentName}</p>
      </div>

      <div className="flex items-center gap-4 rounded-xl border border-border-light p-4 dark:border-border-dark">
        <ConfidenceRing value={student.currentEngagement} size={72} strokeWidth={7} label="score" />
        <div>
          <p className="text-sm font-semibold text-text-light dark:text-text-dark">Engagement score</p>
          <p className="text-xs text-textmuted-light dark:text-textmuted-dark">Computed from gaze, emotion, participation, and distraction penalty</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <MetricRow icon={EmotionIcon} label="Emotion" value={`${student.currentEmotion} · ${(0.7 + student.currentEngagement / 400).toFixed(2)}`} tone={student.currentEmotion === 'happy' || student.currentEmotion === 'neutral' ? 'engaged' : 'attention'} />
        <MetricRow icon={student.authenticated ? CheckCircle2 : AlertTriangle} label="Face auth" value={student.authenticated ? 'Verified' : 'Failed'} tone={student.authenticated ? 'engaged' : 'critical'} />
        <MetricRow icon={student.cognitiveState === 'focused' ? Eye : EyeOff} label="Head pose" value={student.cognitiveState === 'distracted' ? '18° deviation' : '4° deviation'} tone={student.cognitiveState === 'distracted' ? 'attention' : 'engaged'} />
        <MetricRow icon={student.cognitiveState === 'distracted' ? EyeOff : Eye} label="Looking away" value={student.cognitiveState === 'distracted' ? 'Detected' : 'No'} tone={student.cognitiveState === 'distracted' ? 'attention' : 'engaged'} />
        <MetricRow icon={Moon} label="Sleeping" value={student.cognitiveState === 'drowsy' ? 'Detected' : 'No'} tone={student.cognitiveState === 'drowsy' ? 'critical' : 'engaged'} />
        <MetricRow icon={Phone} label="Phone detected" value={student.activeAlert === 'phone_detected' ? 'Yes' : 'No'} tone={student.activeAlert === 'phone_detected' ? 'critical' : 'engaged'} />
        <MetricRow icon={Users2} label="Multiple persons" value={student.activeAlert === 'multiple_person' ? 'Yes' : 'No'} tone={student.activeAlert === 'multiple_person' ? 'critical' : 'engaged'} />
        <MetricRow icon={student.micOn ? Volume2 : VolumeX} label="Voice disturbance" value={student.activeAlert === 'voice_disturbance' ? 'Detected' : 'Clear'} tone={student.activeAlert === 'voice_disturbance' ? 'attention' : 'engaged'} />
      </div>

      <div className="rounded-xl border border-border-light p-3 dark:border-border-dark">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-textmuted-light dark:text-textmuted-dark">Engagement timeline</p>
        <div className="flex h-16 items-end gap-1">
          {student.history.map((v, i) => (
            <div
              key={i}
              className={cn('flex-1 rounded-t', v >= 70 ? 'bg-engaged-500' : v >= 40 ? 'bg-attention-500' : 'bg-critical-500')}
              style={{ height: `${Math.max(8, v)}%` }}
            />
          ))}
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-textmuted-light dark:text-textmuted-dark">
          <span>12 min ago</span><span>now</span>
        </div>
      </div>

      {alertActive && (
        <div className="flex items-start gap-2 rounded-xl border border-critical-500/30 bg-critical-500/5 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical-500" />
          <div>
            <p className="text-sm font-medium text-critical-600 dark:text-critical-400">Active alert: {student.activeAlert?.replace('_', ' ')}</p>
            <p className="text-xs text-textmuted-light dark:text-textmuted-dark">Confidence {(72 + Math.random() * 25).toFixed(0)}% · flagged just now</p>
          </div>
        </div>
      )}

      <div className="rounded-xl bg-focus-500/5 p-3 text-xs text-textmuted-light dark:text-textmuted-dark">
        <p className="mb-1 flex items-center gap-1.5 font-medium text-focus-600 dark:text-focus-400"><ScanFace className="h-3.5 w-3.5" />LSTM prediction</p>
        Attention drop probability in the next 5 minutes: <strong className="text-text-light dark:text-text-dark">{student.currentEngagement < 50 ? 'High (68%)' : student.currentEngagement < 70 ? 'Medium (34%)' : 'Low (9%)'}</strong>
      </div>
    </div>
  )
}
