import {
  Eye,
  EyeOff,
  Smile,
  Frown,
  Meh,
  ScanFace,
  Volume2,
  VolumeX,
  Phone,
  Users2,
  Moon,
  AlertTriangle,
  CheckCircle2,
  Activity,
  Eye as BlinkIcon,
} from 'lucide-react'

import { ConfidenceRing } from './ConfidenceRing'
import { Badge } from '@/components/ui/Badge'
import type { StudentLiveState } from '@/types/domain'
import { cn, predictionLabelText, predictionLabelTone } from '@/lib/utils'

const EMOTION_ICON = {
  neutral: Meh,
  happy: Smile,
  confused: Meh,
  bored: Frown,
  frustrated: Frown,
  surprised: Smile,
  sad: Frown,
} as const

function MetricRow({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Eye
  label: string
  value: string
  tone: 'engaged' | 'attention' | 'critical' | 'neutral'
}) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg bg-black/5 px-3 py-2 dark:bg-white/5">
      <div className="flex min-w-0 items-center gap-2">
        <Icon className="h-4 w-4 shrink-0 text-textmuted-light dark:text-textmuted-dark" />

        <span className="text-xs text-textmuted-light dark:text-textmuted-dark">
          {label}
        </span>
      </div>

      <Badge variant={tone}>
        {value}
      </Badge>
    </div>
  )
}

/**
 * Detailed AI readout for a single student.
 *
 * Uses the REAL AI values coming from:
 *
 * /live-monitor
 *
 * including:
 * - emotion
 * - engagement
 * - face authentication
 * - head pose
 * - gaze
 * - blink count
 * - drowsiness
 * - phone detection
 * - person count
 * - voice disturbance
 */
export function AIMonitoringPanel({
  student,
}: {
  student: StudentLiveState
}) {
  const EmotionIcon =
    EMOTION_ICON[
      student.currentEmotion as keyof typeof EMOTION_ICON
    ] ?? Meh

  const alertActive = Boolean(student.activeAlert)

  // ------------------------------------------------------------
  // REAL AI VALUES
  // ------------------------------------------------------------

  const aiStudent = student as StudentLiveState & {
    blinkCount?: number
    headPose?: string
    gaze?: string
    phoneDetected?: boolean
    personCount?: number
    engagementStatus?: string
  }

  const blinkCount = aiStudent.blinkCount ?? 0

  const headPose =
    aiStudent.headPose ?? 'Forward'

  const gaze =
    aiStudent.gaze ?? 'Center'

  const phoneDetected =
    aiStudent.phoneDetected ?? false

  const personCount =
    aiStudent.personCount ?? 1

  const engagementStatus =
    aiStudent.engagementStatus ??
    (student.currentEngagement >= 70
      ? 'Focused'
      : student.currentEngagement >= 40
        ? 'Drifting'
        : 'Needs attention')

  const isLookingForward =
    headPose.toLowerCase().includes('forward')

  const isGazeCenter =
    gaze.toLowerCase() === 'center'

  const isDrowsy =
    student.cognitiveState === 'drowsy'

  const multiplePersons =
    personCount > 1

  const noPersonDetected =
    personCount === 0 || student.activeAlert === 'no_person_detected'

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-3">

      {/* ============================================================
          HEADER
      ============================================================ */}

      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-focus-500" />

        <p className="text-sm font-semibold text-text-light dark:text-text-dark">
          AI Monitoring — {student.studentName}
        </p>
      </div>

      {/* ============================================================
          ENGAGEMENT SCORE
      ============================================================ */}

      <div className="flex items-center gap-4 rounded-xl border border-border-light p-4 dark:border-border-dark">

        <ConfidenceRing
          value={student.currentEngagement}
          size={72}
          strokeWidth={7}
          label="score"
        />

        <div className="min-w-0">
          <p className="text-sm font-semibold text-text-light dark:text-text-dark">
            Engagement score
          </p>

          <p className="text-xs text-textmuted-light dark:text-textmuted-dark">
            Computed from gaze, emotion, participation, and distraction penalty
          </p>

          <div className="mt-2">
            <Badge
              variant={
                student.currentEngagement >= 70
                  ? 'engaged'
                  : student.currentEngagement >= 40
                    ? 'attention'
                    : 'critical'
              }
            >
              {engagementStatus}
            </Badge>
          </div>
        </div>
      </div>

      {/* ============================================================
          REAL AI METRICS
      ============================================================ */}

      <div className="grid grid-cols-2 gap-2">

        {/* Emotion */}
        <MetricRow
          icon={EmotionIcon}
          label="Emotion"
          value={student.currentEmotion}
          tone={
            student.currentEmotion === 'happy' ||
            student.currentEmotion === 'neutral'
              ? 'engaged'
              : 'attention'
          }
        />

        {/* Face authentication */}
        <MetricRow
          icon={
            student.authenticated
              ? CheckCircle2
              : AlertTriangle
          }
          label="Face auth"
          value={
            student.authenticated
              ? 'Verified'
              : 'Failed'
          }
          tone={
            student.authenticated
              ? 'engaged'
              : 'critical'
          }
        />

        {/* Head pose */}
        <MetricRow
          icon={
            isLookingForward
              ? Eye
              : EyeOff
          }
          label="Head pose"
          value={headPose}
          tone={
            isLookingForward
              ? 'engaged'
              : 'attention'
          }
        />

        {/* Gaze */}
        <MetricRow
          icon={
            isGazeCenter
              ? Eye
              : EyeOff
          }
          label="Gaze"
          value={gaze}
          tone={
            isGazeCenter
              ? 'engaged'
              : 'attention'
          }
        />

        {/* Sleeping / drowsiness */}
        <MetricRow
          icon={Moon}
          label="Sleeping"
          value={
            isDrowsy
              ? 'Detected'
              : 'No'
          }
          tone={
            isDrowsy
              ? 'critical'
              : 'engaged'
          }
        />

        {/* Phone */}
        <MetricRow
          icon={Phone}
          label="Phone detected"
          value={
            phoneDetected
              ? 'Yes'
              : 'No'
          }
          tone={
            phoneDetected
              ? 'critical'
              : 'engaged'
          }
        />

        {/* Person count */}
        <MetricRow
          icon={Users2}
          label="Persons"
          value={
            noPersonDetected
              ? 'None'
              : String(personCount)
          }
          tone={
            multiplePersons || noPersonDetected
              ? 'critical'
              : 'engaged'
          }
        />

        {/* Blink count */}
        <MetricRow
          icon={BlinkIcon}
          label="Blink count"
          value={String(blinkCount)}
          tone="neutral"
        />

        {/* Voice */}
        <MetricRow
          icon={
            student.micOn
              ? Volume2
              : VolumeX
          }
          label="Voice disturbance"
          value={
            student.activeAlert ===
            'voice_disturbance'
              ? 'Detected'
              : 'Clear'
          }
          tone={
            student.activeAlert ===
            'voice_disturbance'
              ? 'attention'
              : 'engaged'
          }
        />
      </div>

      {/* ============================================================
          ENGAGEMENT TIMELINE
      ============================================================ */}

      <div className="rounded-xl border border-border-light p-3 dark:border-border-dark">

        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-textmuted-light dark:text-textmuted-dark">
          Engagement timeline
        </p>

        <div className="flex h-16 items-end gap-1">

          {student.history.map((value, index) => (
            <div
              key={index}
              className={cn(
                'flex-1 rounded-t',
                value >= 70
                  ? 'bg-engaged-500'
                  : value >= 40
                    ? 'bg-attention-500'
                    : 'bg-critical-500',
              )}
              style={{
                height: `${Math.max(8, value)}%`,
              }}
            />
          ))}

        </div>

        <div className="mt-1 flex justify-between text-[10px] text-textmuted-light dark:text-textmuted-dark">
          <span>12 min ago</span>
          <span>now</span>
        </div>
      </div>

      {/* ============================================================
          ACTIVE ALERT
      ============================================================ */}

      {alertActive && (
        <div className="flex items-start gap-2 rounded-xl border border-critical-500/30 bg-critical-500/5 p-3">

          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical-500" />

          <div>

            <p className="text-sm font-medium text-critical-600 dark:text-critical-400">
              Active alert:{' '}
              {student.activeAlert?.replaceAll(
                '_',
                ' ',
              )}
            </p>

            <p className="text-xs text-textmuted-light dark:text-textmuted-dark">
              Active backend alert · flagged just now
            </p>

          </div>
        </div>
      )}

      {/* ============================================================
          AI STATUS SUMMARY
      ============================================================ */}

      <div className="rounded-xl border border-border-light bg-focus-500/5 p-3 dark:border-border-dark">

        <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-focus-600 dark:text-focus-400">
          <ScanFace className="h-3.5 w-3.5" />

          Real-time AI status
        </p>

        <div className="grid grid-cols-2 gap-2 text-xs">

          <div>
            <span className="text-textmuted-light dark:text-textmuted-dark">
              Emotion
            </span>

            <p className="font-medium capitalize text-text-light dark:text-text-dark">
              {student.currentEmotion}
            </p>
          </div>

          <div>
            <span className="text-textmuted-light dark:text-textmuted-dark">
              Engagement
            </span>

            <p className="font-medium text-text-light dark:text-text-dark">
              {student.currentEngagement}%
            </p>
          </div>

          <div>
            <span className="text-textmuted-light dark:text-textmuted-dark">
              Head
            </span>

            <p className="font-medium text-text-light dark:text-text-dark">
              {headPose}
            </p>
          </div>

          <div>
            <span className="text-textmuted-light dark:text-textmuted-dark">
              Gaze
            </span>

            <p className="font-medium text-text-light dark:text-text-dark">
              {gaze}
            </p>
          </div>

        </div>
      </div>

      {/* ============================================================
          ENGAGEMENT PREDICTION
          Real LSTM-based future-engagement prediction (see
          EngagementPredictionService on the backend) -- never a
          fabricated number. predictedEngagement/predictionLabel are
          undefined/'unavailable' whenever a real prediction hasn't
          actually been produced this cycle.
      ============================================================ */}

      <div className="rounded-xl bg-focus-500/5 p-3 text-xs text-textmuted-light dark:text-textmuted-dark">

        <p className="mb-2 flex items-center gap-1.5 font-medium text-focus-600 dark:text-focus-400">
          <ScanFace className="h-3.5 w-3.5" />

          Engagement prediction
        </p>

        {typeof student.predictedEngagement === 'number' ? (
          <>
            <p className="text-text-light dark:text-text-dark">
              Predicted engagement:{' '}
              <strong>{Math.round(student.predictedEngagement)}%</strong>
            </p>

            <div className="mt-2">
              <Badge variant={predictionLabelTone(student.predictionLabel)}>
                {predictionLabelText(student.predictionLabel)}
              </Badge>
            </div>
          </>
        ) : (
          <p>
            {student.predictionStatus === 'paused_no_person'
              ? 'Prediction paused -- no person currently in frame.'
              : student.predictionStatus === 'insufficient_data'
                ? 'Collecting engagement data... prediction will appear once enough history is available.'
                : 'Prediction unavailable.'}
          </p>
        )}

      </div>

    </div>
  )
}