import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatDateTime(iso: string) {
  return `${formatDate(iso)} · ${formatTime(iso)}`
}

export function relativeTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const diffMin = Math.round(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.round(diffHr / 24)
  return `${diffDay}d ago`
}

export function clamp(n: number, min: number, max: number) {
  return Math.min(Math.max(n, min), max)
}

export function engagementTone(score: number): 'engaged' | 'attention' | 'critical' {
  if (score >= 70) return 'engaged'
  if (score >= 40) return 'attention'
  return 'critical'
}

// Shared source of truth for how a backend-computed prediction "label"
// (see types/domain.ts PredictionLabel / backend prediction_state_label())
// is described in the UI, so the student dashboard, teacher participants
// list, and AI monitoring panel never drift out of sync with each other
// or hardcode their own threshold-derived copy.
export function predictionLabelText(
  label: 'stable' | 'attention_may_decrease' | 'attention_drop_predicted' | 'unavailable' | undefined,
): string {
  switch (label) {
    case 'stable':
      return 'Stable'
    case 'attention_may_decrease':
      return 'Attention may decrease'
    case 'attention_drop_predicted':
      return 'Attention drop predicted'
    default:
      return 'Prediction unavailable'
  }
}

export function predictionLabelTone(
  label: 'stable' | 'attention_may_decrease' | 'attention_drop_predicted' | 'unavailable' | undefined,
): 'engaged' | 'attention' | 'critical' | 'neutral' {
  switch (label) {
    case 'stable':
      return 'engaged'
    case 'attention_may_decrease':
      return 'attention'
    case 'attention_drop_predicted':
      return 'critical'
    default:
      return 'neutral'
  }
}

// Shared source of truth for the HISTORICAL/FUTURE engagement prediction
// (a SEPARATE feature from predictionLabelText/Tone above -- see
// types/domain.ts FutureEngagementStatusLabel / backend
// future_prediction_status_label()) -- keeps the student dashboard and
// teacher's Future Engagement Prediction list from drifting apart.
export function futureEngagementLabelText(
  label: 'stable' | 'needs_attention' | 'at_risk' | 'unavailable' | undefined,
): string {
  switch (label) {
    case 'stable':
      return 'Stable'
    case 'needs_attention':
      return 'Needs attention'
    case 'at_risk':
      return 'At risk'
    default:
      return 'Unavailable'
  }
}

export function futureEngagementLabelTone(
  label: 'stable' | 'needs_attention' | 'at_risk' | 'unavailable' | undefined,
): 'engaged' | 'attention' | 'critical' | 'neutral' {
  switch (label) {
    case 'stable':
      return 'engaged'
    case 'needs_attention':
      return 'attention'
    case 'at_risk':
      return 'critical'
    default:
      return 'neutral'
  }
}

// Session-level, rule-based Cognitive State summary (a SEPARATE, new
// feature from the LSTM engagement prediction above -- see
// backend/services/cognitive_state_service.py for the full deterministic
// classification method and why it is explicitly NOT a trained ML model).
// Computed once when a class session ends and shown only in the
// teacher's post-class report -- never during the live class, never to
// the student.
export function cognitiveStateText(
  state: 'focused' | 'neutral' | 'distracted' | 'drowsy' | null | undefined,
): string {
  switch (state) {
    case 'focused':
      return 'Focused'
    case 'neutral':
      return 'Neutral'
    case 'distracted':
      return 'Distracted'
    case 'drowsy':
      return 'Drowsy'
    default:
      return 'Not available'
  }
}

export function cognitiveStateTone(
  state: 'focused' | 'neutral' | 'distracted' | 'drowsy' | null | undefined,
): 'engaged' | 'attention' | 'critical' | 'neutral' {
  switch (state) {
    case 'focused':
      return 'engaged'
    case 'neutral':
      return 'attention'
    case 'distracted':
      return 'critical'
    case 'drowsy':
      return 'critical'
    default:
      return 'neutral'
  }
}

export function initials(name: string) {
  return name
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}
