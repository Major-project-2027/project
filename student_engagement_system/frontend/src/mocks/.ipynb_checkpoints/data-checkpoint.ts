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

export function generateClasses(count = 0): ClassSession[] {
  return []
}

/**
 * A tiny in-memory "database" for classes, seeded once per browser session.
 * Real apps would drop this in favor of the backend being the source of
 * truth — this exists purely so scheduling/starting a class in this mock
 * phase actually persists instead of resetting on every refetch.
 */
let classesStore: ClassSession[] = []
type SessionEngagement = {
  studentId: string
  studentName: string
  history: number[]
}

const sessionEngagementStore: Record<string, SessionEngagement[]> = {}
const CLASSES_STORAGE_KEY = "student_engagement_classes"



function loadClassesFromStorage(): ClassSession[] {
  try {
    const stored = localStorage.getItem(CLASSES_STORAGE_KEY)

    if (!stored) {
      return []
    }

    const parsed = JSON.parse(stored)

    return Array.isArray(parsed)
      ? parsed
      : []
  } catch {
    return []
  }
}

function saveClassesToStorage(classes: ClassSession[]) {
  try {
    localStorage.setItem(
      CLASSES_STORAGE_KEY,
      JSON.stringify(classes)
    )
  } catch {
    // Ignore storage errors
  }
}

classesStore = loadClassesFromStorage()

export function getClassesStore(): ClassSession[] {
  classesStore = loadClassesFromStorage()
  return classesStore
}
export function recordStudentEngagement(
  classId: string,
  studentId: string,
  studentName: string,
  engagement: number,
) {
  if (!sessionEngagementStore[classId]) {
    sessionEngagementStore[classId] = []
  }

  let student = sessionEngagementStore[classId].find(
    (s) => s.studentId === studentId
  )

  if (!student) {
    student = {
      studentId,
      studentName,
      history: [],
    }

    sessionEngagementStore[classId].push(student)
  }

  student.history.push(Number(engagement))
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
  classesStore = [newClass, ...getClassesStore()]
      saveClassesToStorage(classesStore)

  return newClass
}

export function startClassInStore(
  id: string
): ClassSession | undefined {
  classesStore = getClassesStore().map((c) =>
    c.id === id
      ? {
          ...c,
          status: "live",
          scheduledStart:
            new Date().toISOString(),
          studentsPresent: 0,
          avgEngagement: 0,
        }
      : c
  )

  saveClassesToStorage(classesStore)

  return classesStore.find(
    (c) => c.id === id
  )
}

export function endClassInStore(
  id: string,
): ClassSession | undefined {
  const classSession = getClassesStore().find(
    (c) => c.id === id,
  )

  if (!classSession) {
    return undefined
  }

  // Finalize attendance ONLY when teacher ends class.
  const attendanceRecords =
    finalizeClassAttendance(id)

  const sessionStudents =
    sessionEngagementStore[id] ?? []

  const classAverage =
    sessionStudents.length > 0
      ? sessionStudents.reduce(
          (sum, student) => {
            if (student.history.length === 0) {
              return sum
            }

            const studentAverage =
              student.history.reduce(
                (a, b) => a + b,
                0,
              ) / student.history.length

            return sum + studentAverage
          },
          0,
        ) / sessionStudents.length
      : 0

  classesStore = getClassesStore().map((c) =>
    c.id === id
      ? {
          ...c,
          status: 'completed',
          recordingAvailable: true,
          studentsPresent: attendanceRecords.length,
          avgEngagement: Math.round(classAverage),
        }
      : c,
  )

  saveClassesToStorage(classesStore)

  // Clear live engagement after the class is finalized.
  delete sessionEngagementStore[id]

  return classesStore.find(
    (c) => c.id === id,
  )
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

const ATTENDANCE_STORAGE_KEY = 'student_engagement_attendance'

function loadAttendanceFromStorage(): AttendanceRecord[] {
  try {
    const stored = localStorage.getItem(ATTENDANCE_STORAGE_KEY)

    if (!stored) {
      return []
    }

    const parsed = JSON.parse(stored)

    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveAttendanceToStorage(
  records: AttendanceRecord[],
) {
  try {
    localStorage.setItem(
      ATTENDANCE_STORAGE_KEY,
      JSON.stringify(records),
    )
  } catch {
    // Ignore storage errors
  }
}

export function finalizeClassAttendance(
  classId: string,
): AttendanceRecord[] {
  const classSession = getClassesStore().find(
    (c) => c.id === classId,
  )

  if (!classSession) {
    return []
  }

  const sessionStudents =
    sessionEngagementStore[classId] ?? []

  const newRecords: AttendanceRecord[] = []

  for (const student of sessionStudents) {
    if (student.history.length === 0) {
      continue
    }

    // Calculate the student's average engagement
    // throughout the entire class session.
    const averageEngagement =
      student.history.reduce(
        (sum, value) => sum + value,
        0,
      ) / student.history.length

    // Engagement at the moment the teacher ended the class.
    const latestEngagement =
      student.history[student.history.length - 1]

    /*
      ATTENDANCE RULE

      Attendance is awarded ONLY after the teacher
      ends the class AND:

      1. Latest engagement > 50%
      2. Average engagement throughout the session > 50%

      If either condition fails, no attendance record
      is created for that student.
    */
    if (
      latestEngagement > 50 &&
      averageEngagement > 50
    ) {
      newRecords.push({
        id: `attendance-${classId}-${student.studentId}`,
        studentId: student.studentId,
        studentName: student.studentName,
        classId,
        className: classSession.title,
        date: new Date().toISOString(),
        status: 'present',
        joinTime: undefined,
        leaveTime: new Date().toISOString(),
        engagementAvg: Math.round(averageEngagement),
      })
    }
  }

  /*
    IMPORTANT:

    Always read the latest attendance from localStorage.
    Do not use a separate in-memory attendanceStore because
    teacher and student pages may be running in different
    browser tabs.
  */
  const existingAttendance =
    loadAttendanceFromStorage()

  const updatedAttendance = [
    ...existingAttendance.filter(
      (record) => record.classId !== classId,
    ),
    ...newRecords,
  ]

  saveAttendanceToStorage(updatedAttendance)

  return newRecords
}

export function generateAttendance(): AttendanceRecord[] {
  // Always return the latest data from localStorage.
  // This allows the student dashboard/tab to see attendance
  // created when the teacher ended the class.
  return loadAttendanceFromStorage()
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

export function generateNotifications(count = 0): AppNotification[] {
  return []
}

export function generateTests(): Test[] {
  return []
}

export { STUDENT_NAMES }
