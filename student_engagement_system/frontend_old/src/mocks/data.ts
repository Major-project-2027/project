import type {
  AIAlert,
  AppNotification,
  AttendanceRecord,
  BehaviorBreakdown,
  ClassSession,
  EngagementTrendPoint,
  StudentLiveState,
  Test,
  TeacherProfile,
  StudentProfile,
} from '@/types/domain'

const STUDENT_NAMES = [
  'Aarav Mehta', 'Diya Sharma', 'Kabir Nair', 'Isha Reddy', 'Vihaan Rao',
  'Ananya Iyer', 'Arjun Pillai', 'Myra Kulkarni', 'Reyansh Gupta', 'Sara Menon',
  'Advait Joshi', 'Riya Kapoor', 'Ayaan Khan', 'Ira Desai', 'Vivaan Malhotra',
]

const COVER_COLORS = ['#4F5DFF', '#22C55E', '#F5A524', '#F0466E', '#7C86FF']

function seededRandom(seed: number) {
  let s = seed
  return () => {
    s = (s * 9301 + 49297) % 233280
    return s / 233280
  }
}
const rand = seededRandom(42)

export const currentTeacher: TeacherProfile = {
  id: 't-1001',
  name: 'Dr. Kavita Rao',
  email: 'kavita.rao@bit.edu',
  role: 'teacher',
  department: 'Computer Science & Engineering',
  subjects: ['Machine Learning', 'Data Structures', 'Computer Vision'],
  totalClasses: 128,
  createdAt: '2023-06-01T00:00:00Z',
}

export const currentStudent: StudentProfile = {
  id: 's-2044',
  name: 'Rohan Verma',
  email: 'rohan.verma@bit.edu',
  role: 'student',
  rollNumber: '1BI22CS091',
  cameraEnabled: true,
  micEnabled: true,
  faceEnrolled: true,
  createdAt: '2023-08-14T00:00:00Z',
}

export function generateClasses(count = 8): ClassSession[] {
  const subjects = ['Machine Learning', 'Data Structures', 'Computer Vision', 'Operating Systems', 'DBMS']
  const now = Date.now()
  return Array.from({ length: count }).map((_, i) => {
    const offsetHours = (i - 2) * 5
    const start = new Date(now + offsetHours * 3600 * 1000)
    const end = new Date(start.getTime() + 50 * 60 * 1000)
    const status: ClassSession['status'] = offsetHours < -2 ? 'completed' : offsetHours < 1 && offsetHours > -1 ? 'live' : 'scheduled'
    return {
      id: `class-${i}`,
      title: `${subjects[i % subjects.length]} — Unit ${i + 1}`,
      subject: subjects[i % subjects.length],
      teacherId: currentTeacher.id,
      teacherName: currentTeacher.name,
      scheduledStart: start.toISOString(),
      scheduledEnd: end.toISOString(),
      status,
      studentsEnrolled: 42,
      studentsPresent: status !== 'scheduled' ? 30 + Math.floor(rand() * 10) : undefined,
      avgEngagement: status !== 'scheduled' ? 55 + Math.floor(rand() * 35) : undefined,
      coverColor: COVER_COLORS[i % COVER_COLORS.length],
      recordingAvailable: status === 'completed',
    }
  })
}

/**
 * A tiny in-memory "database" for classes, seeded once per browser session.
 * Real apps would drop this in favor of the backend being the source of
 * truth — this exists purely so scheduling/starting a class in this mock
 * phase actually persists instead of resetting on every refetch.
 */
let classesStore: ClassSession[] = generateClasses(10)

export function getClassesStore(): ClassSession[] {
  return classesStore
}

export function createClassInStore(input: {
  title: string
  subject: string
  scheduledStart: string
  startNow: boolean
}): ClassSession {
  const start = input.startNow ? new Date() : new Date(input.scheduledStart)
  const end = new Date(start.getTime() + 50 * 60 * 1000)
  const newClass: ClassSession = {
    id: `class-${Date.now()}`,
    title: input.title || `${input.subject} — New Session`,
    subject: input.subject || 'General',
    teacherId: currentTeacher.id,
    teacherName: currentTeacher.name,
    scheduledStart: start.toISOString(),
    scheduledEnd: end.toISOString(),
    status: input.startNow ? 'live' : 'scheduled',
    studentsEnrolled: 42,
    studentsPresent: input.startNow ? 0 : undefined,
    avgEngagement: input.startNow ? 0 : undefined,
    coverColor: COVER_COLORS[classesStore.length % COVER_COLORS.length],
    recordingAvailable: false,
  }
  classesStore = [newClass, ...classesStore]
  return newClass
}

export function startClassInStore(id: string): ClassSession | undefined {
  classesStore = classesStore.map((c) =>
    c.id === id ? { ...c, status: 'live', scheduledStart: new Date().toISOString(), studentsPresent: 0, avgEngagement: 0 } : c,
  )
  return classesStore.find((c) => c.id === id)
}

export function endClassInStore(id: string): ClassSession | undefined {
  classesStore = classesStore.map((c) => (c.id === id ? { ...c, status: 'completed', recordingAvailable: true } : c))
  return classesStore.find((c) => c.id === id)
}

export function generateLiveStudents(count = 15): StudentLiveState[] {
  const emotions: StudentLiveState['currentEmotion'][] = ['neutral', 'happy', 'confused', 'bored', 'frustrated', 'surprised']
  const cognitive: StudentLiveState['cognitiveState'][] = ['focused', 'distracted', 'drowsy', 'confused']
  return Array.from({ length: count }).map((_, i) => {
    const base = 40 + Math.floor(rand() * 55)
    const history = Array.from({ length: 12 }).map(() => Math.min(100, Math.max(10, base + Math.floor((rand() - 0.5) * 30))))
    const hasAlert = rand() > 0.78
    const alertTypes: NonNullable<StudentLiveState['activeAlert']>[] = ['looking_away', 'drowsiness', 'phone_detected', 'multiple_person', 'voice_disturbance']
    return {
      studentId: `s-${2000 + i}`,
      studentName: STUDENT_NAMES[i % STUDENT_NAMES.length],
      cameraOn: rand() > 0.1,
      micOn: rand() > 0.6,
      handRaised: rand() > 0.9,
      currentEngagement: base,
      currentEmotion: emotions[Math.floor(rand() * emotions.length)],
      cognitiveState: cognitive[Math.floor(rand() * cognitive.length)],
      authenticated: rand() > 0.05,
      activeAlert: hasAlert ? alertTypes[Math.floor(rand() * alertTypes.length)] : undefined,
      history,
    }
  })
}

export function generateAlerts(count = 20): AIAlert[] {
  const types: AIAlert['type'][] = [
    'looking_away', 'drowsiness', 'phone_detected', 'multiple_person',
    'face_auth_failed', 'voice_disturbance', 'camera_off', 'attention_drop_predicted',
  ]
  const messages: Record<AIAlert['type'], string> = {
    looking_away: 'Gaze off-screen for over 12 seconds',
    drowsiness: 'Eye closure pattern suggests drowsiness',
    phone_detected: 'Mobile device detected in frame',
    multiple_person: 'A second person was detected in frame',
    face_auth_failed: 'Face authentication could not verify identity',
    voice_disturbance: 'Background voice disturbance detected',
    camera_off: 'Camera turned off during a live session',
    attention_drop_predicted: 'LSTM model forecasts an attention drop in the next 5 minutes',
    no_face_detected: 'No face detected in frame',
  }
  const severity: Record<AIAlert['type'], AIAlert['severity']> = {
    looking_away: 'warning',
    drowsiness: 'warning',
    phone_detected: 'critical',
    multiple_person: 'critical',
    face_auth_failed: 'critical',
    voice_disturbance: 'info',
    camera_off: 'info',
    attention_drop_predicted: 'warning',
    no_face_detected: 'info',
  }
  const now = Date.now()
  return Array.from({ length: count }).map((_, i) => {
    const type = types[Math.floor(rand() * types.length)]
    const studentIdx = Math.floor(rand() * STUDENT_NAMES.length)
    return {
      id: `alert-${i}`,
      studentId: `s-${2000 + studentIdx}`,
      studentName: STUDENT_NAMES[studentIdx],
      classId: 'class-2',
      type,
      severity: severity[type],
      message: messages[type],
      timestamp: new Date(now - i * 4 * 60 * 1000).toISOString(),
      confidence: 0.7 + rand() * 0.29,
      acknowledged: rand() > 0.6,
    }
  })
}

export function generateAttendance(count = 15): AttendanceRecord[] {
  const statuses: AttendanceRecord['status'][] = ['present', 'present', 'present', 'late', 'absent']
  return Array.from({ length: count }).map((_, i) => ({
    id: `att-${i}`,
    studentId: `s-${2000 + i}`,
    studentName: STUDENT_NAMES[i % STUDENT_NAMES.length],
    classId: 'class-2',
    className: 'Machine Learning — Unit 3',
    date: new Date(Date.now() - 0).toISOString(),
    status: statuses[Math.floor(rand() * statuses.length)],
    joinTime: '09:02 AM',
    leaveTime: '09:48 AM',
    engagementAvg: 45 + Math.floor(rand() * 45),
  }))
}

export function generateEngagementTrend(days = 14): EngagementTrendPoint[] {
  return Array.from({ length: days }).map((_, i) => ({
    label: new Date(Date.now() - (days - i) * 86400000).toLocaleDateString([], { month: 'short', day: 'numeric' }),
    avgEngagement: 55 + Math.round(Math.sin(i / 2) * 15 + rand() * 10),
    attendanceRate: 80 + Math.round(Math.sin(i / 3) * 10 + rand() * 8),
  }))
}

export const behaviorBreakdown: BehaviorBreakdown[] = [
  { label: 'Focused', value: 58, color: '#22C55E' },
  { label: 'Distracted', value: 22, color: '#F5A524' },
  { label: 'Drowsy', value: 12, color: '#F0466E' },
  { label: 'Confused', value: 8, color: '#7C86FF' },
]

export function generateNotifications(count = 12): AppNotification[] {
  const now = Date.now()
  const samples = [
    { category: 'ai_alert' as const, title: 'Phone detected', message: 'Aarav Mehta — mobile device detected during Machine Learning class.', severity: 'critical' as const },
    { category: 'ai_alert' as const, title: 'Drowsiness detected', message: 'Myra Kulkarni shows signs of drowsiness in the current session.', severity: 'warning' as const },
    { category: 'attendance' as const, title: 'Attendance warning', message: 'Ayaan Khan has missed 3 consecutive classes.', severity: 'warning' as const },
    { category: 'class' as const, title: 'Class starting soon', message: 'Data Structures begins in 10 minutes.', severity: 'info' as const },
    { category: 'system' as const, title: 'Weekly report ready', message: 'Your weekly engagement report has been generated.', severity: 'info' as const },
    { category: 'ai_alert' as const, title: 'Multiple persons detected', message: 'A second person was detected behind Kabir Nair.', severity: 'critical' as const },
    { category: 'ai_alert' as const, title: 'Camera turned off', message: 'Isha Reddy turned off her camera without permission.', severity: 'info' as const },
  ]
  return Array.from({ length: count }).map((_, i) => {
    const s = samples[i % samples.length]
    return {
      id: `notif-${i}`,
      category: s.category,
      title: s.title,
      message: s.message,
      severity: s.severity,
      timestamp: new Date(now - i * 22 * 60 * 1000).toISOString(),
      read: i > 3,
    }
  })
}

export function generateTests(): Test[] {
  return [
    {
      id: 'test-1',
      title: 'Neural Networks — Mid Unit Quiz',
      subject: 'Machine Learning',
      classId: 'class-1',
      durationMinutes: 30,
      totalMarks: 20,
      scheduledStart: new Date(Date.now() + 3600 * 1000).toISOString(),
      status: 'scheduled',
      proctoringEnabled: true,
      questions: [
        { id: 'q1', type: 'mcq', prompt: 'Which activation function outputs values between 0 and 1?', options: ['ReLU', 'Sigmoid', 'Tanh', 'Softmax'], correctOptionIndex: 1, marks: 2 },
        { id: 'q2', type: 'true_false', prompt: 'LSTMs are designed to mitigate the vanishing gradient problem.', options: ['True', 'False'], correctOptionIndex: 0, marks: 1 },
        { id: 'q3', type: 'short_answer', prompt: 'Define the vanishing gradient problem in one sentence.', marks: 3 },
      ],
    },
    {
      id: 'test-2',
      title: 'Computer Vision — Final Assessment',
      subject: 'Computer Vision',
      classId: 'class-3',
      durationMinutes: 45,
      totalMarks: 40,
      scheduledStart: new Date(Date.now() - 86400000).toISOString(),
      status: 'completed',
      proctoringEnabled: true,
      questions: [],
    },
  ]
}

export { STUDENT_NAMES }
