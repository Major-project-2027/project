// ============================================================================
// Core domain types — the single source of truth for shapes returned by the
// (future) backend APIs. All mock data and components conform to these.
// ============================================================================

export type UserRole = 'teacher' | 'student' | 'admin'

export interface User {
  id: string
  name: string
  email: string
  role: UserRole
  avatarUrl?: string
  department?: string
  createdAt: string
}

export interface TeacherProfile extends User {
  role: 'teacher'
  subjects: string[]
  totalClasses: number
}

export interface StudentProfile extends User {
  role: 'student'
  rollNumber: string
  cameraEnabled: boolean
  micEnabled: boolean
  faceEnrolled: boolean
}

// ---------------------------------------------------------------------------
// Classes / scheduling
// ---------------------------------------------------------------------------

export type ClassStatus = 'scheduled' | 'live' | 'completed' | 'cancelled'

export interface ClassSession {
  id: string
  title: string
  subject: string
  teacherId: string
  teacherName: string
  scheduledStart: string // ISO
  scheduledEnd: string // ISO
  status: ClassStatus
  studentsEnrolled: number
  studentsPresent?: number
  avgEngagement?: number
  coverColor: string
  recordingAvailable?: boolean
}

// Any class with a currently active session, across every teacher --
// used by the student dashboard's "Live Classes" discovery section
// (no class code required to join one of these).
export interface LiveClassSummary {
  sessionId: string
  classId: string
  title: string
  subject: string
  teacherName: string
  startTime: string // ISO
  studentCount: number
}

// ---------------------------------------------------------------------------
// AI Monitoring
// ---------------------------------------------------------------------------

export type EmotionLabel =
  | 'neutral'
  | 'happy'
  | 'confused'
  | 'bored'
  | 'frustrated'
  | 'surprised'
  | 'sad'

export type CognitiveState = 'focused' | 'distracted' | 'drowsy' | 'confused'

export type AlertType =
  | 'looking_away'
  | 'drowsiness'
  | 'phone_detected'
  | 'multiple_person'
  | 'face_auth_failed'
  | 'voice_disturbance'
  | 'camera_off'
  | 'attention_drop_predicted'
  | 'no_face_detected'
  | 'no_person_detected'

export type AlertSeverity = 'info' | 'warning' | 'critical'

export interface AIAlert {
  id: string
  studentId: string
  studentName: string
  classId: string
  type: AlertType
  severity: AlertSeverity
  message: string
  timestamp: string
  confidence: number // 0-1
  acknowledged: boolean
}

export interface EngagementSnapshot {
  studentId: string
  timestamp: string
  engagementScore: number // 0-100
  emotion: EmotionLabel
  emotionConfidence: number
  cognitiveState: CognitiveState
  gazeOnScreen: boolean
  headPoseDeviation: number // degrees
  faceAuthenticated: boolean
  voiceActivity: 'silent' | 'speaking' | 'disturbance'
  objectFlags: Array<'phone' | 'book' | 'second_person' | 'none'>
}

export interface EngagementPrediction {
  studentId: string
  riskLevel: 'low' | 'medium' | 'high'
  probability: number
  predictedForMinute: number
  generatedAt: string
}

export interface StudentLiveState {
  studentId: string
  studentName: string
  avatarUrl?: string

  cameraOn: boolean
  micOn: boolean
  handRaised: boolean

  currentEngagement: number
  currentEmotion: EmotionLabel
  cognitiveState: CognitiveState
  authenticated: boolean
  activeAlert?: AlertType

  history: number[]

  // Real AI monitoring values
  blinkCount?: number
  headPose?: string
  gaze?: string
  phoneDetected?: boolean
  personCount?: number
  engagementStatus?: string
  noPersonDetected?: boolean

  // Future-engagement prediction (LSTM, per session+student -- see
  // EngagementPredictionService on the backend). predictedEngagement is
  // null/undefined whenever a real prediction hasn't actually been
  // produced (insufficient data, no-person pause, or no model loaded) --
  // never a fabricated number.
  predictedEngagement?: number | null
  predictionStatus?: PredictionStatus
  attentionDropPredicted?: boolean
  predictionThreshold?: number
  predictionTimestamp?: string
  // Pre-computed by the backend (prediction_state_label()) from its own
  // centrally-defined thresholds -- the frontend never hardcodes a
  // predicted-engagement cutoff itself, it just displays this.
  predictionLabel?: PredictionLabel
}

// Mirrors the backend's EngagementPredictionService status values exactly
// (services/engagement_prediction_service.py: STATUS_OK/_INSUFFICIENT_DATA/
// _UNAVAILABLE/_PAUSED_NO_PERSON).
export type PredictionStatus =
  | 'ok'
  | 'insufficient_data'
  | 'unavailable'
  | 'paused_no_person'

// Mirrors prediction_state_label() on the backend exactly.
export type PredictionLabel =
  | 'stable'
  | 'attention_may_decrease'
  | 'attention_drop_predicted'
  | 'unavailable'

// ---------------------------------------------------------------------------
// Future Engagement Prediction (HISTORICAL / cross-session -- a SEPARATE
// feature from the live, per-session prediction above. Built from a
// student's own COMPLETED sessions only; see
// backend/services/engagement_prediction_service.py's
// get_future_prediction()).
// ---------------------------------------------------------------------------

// Mirrors get_future_prediction()'s own status values exactly.
export type FutureEngagementStatus =
  | 'insufficient_data'
  | 'ready'
  | 'unavailable'
  | 'error'

// Mirrors future_prediction_status_label() on the backend exactly.
export type FutureEngagementStatusLabel =
  | 'stable'
  | 'needs_attention'
  | 'at_risk'
  | 'unavailable'

export interface FutureEngagementPrediction {
  student_id: number
  status: FutureEngagementStatus
  prediction_score: number | null
  historical_sessions_used: number
  model_version: string | null
  reason: string | null
  generated_at: string | null
  status_label: FutureEngagementStatusLabel
}

// One row in the teacher's Future Engagement Prediction list.
export interface FutureEngagementPredictionRow {
  studentId: number
  studentName: string
  usn: string | null
  status: FutureEngagementStatus
  predictionScore: number | null
  statusLabel: FutureEngagementStatusLabel
  historicalSessionsUsed: number
  generatedAt: string | null
  reason: string | null
}

// ---------------------------------------------------------------------------
// Attendance
// ---------------------------------------------------------------------------

export interface AttendanceRecord {
  id: string
  studentId: string
  studentName: string
  classId: string
  className: string
  date: string
  status: 'present' | 'absent' | 'late' | 'left_early'
  joinTime?: string
  leaveTime?: string
  engagementAvg?: number
}

// ---------------------------------------------------------------------------
// Tests / Assessments
// ---------------------------------------------------------------------------

export type QuestionType = 'mcq' | 'true_false' | 'short_answer' | 'essay'

export interface TestQuestion {
  id: string
  type: QuestionType
  prompt: string
  options?: string[]
  correctOptionIndex?: number
  marks: number
}

export interface Test {
  id: string
  title: string
  subject: string
  classId: string
  durationMinutes: number
  totalMarks: number
  questions: TestQuestion[]
  scheduledStart: string
  status: 'draft' | 'scheduled' | 'live' | 'completed'
  proctoringEnabled: boolean
}

export interface TestSubmission {
  id: string
  testId: string
  studentId: string
  studentName: string
  answers: Record<string, string | number>
  score?: number
  submittedAt?: string
  autoSubmitted: boolean
  integrityFlags: number
}

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

export interface EngagementTrendPoint {
  label: string
  avgEngagement: number
  attendanceRate: number
}

export interface BehaviorBreakdown {
  label: string
  value: number
  color: string
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export type NotificationCategory = 'ai_alert' | 'system' | 'class' | 'attendance'

export interface AppNotification {
  id: string
  category: NotificationCategory
  title: string
  message: string
  timestamp: string
  read: boolean
  severity?: AlertSeverity
  actionUrl?: string
}
