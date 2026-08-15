import { API_BASE_URL, FLASK_API_BASE_URL, simulateNetwork } from './client'
import {
  generateLiveStudents, generateAlerts,
  generateEngagementTrend, generateNotifications, generateTests,
  currentTeacher, currentStudent, behaviorBreakdown,
  getClassesStore, createClassInStore, startClassInStore, endClassInStore,
} from '@/mocks/data'
import type {
  ClassSession, StudentLiveState, AIAlert, AttendanceRecord,
  EngagementTrendPoint, AppNotification, Test, User,
} from '@/types/domain'

// ----------------------------------------------------------------------------
// AUTH        POST /auth/login · POST /auth/register · POST /auth/forgot-password
// ----------------------------------------------------------------------------
export const authApi = {
  login: async (email: string, password: string, role: 'student' | 'teacher') => {
  const normalizedEmail = email.toLowerCase().trim()

  const endpoint =
    role === 'teacher'
      ? '/teacher/login'
      : '/login'

  const response = await fetch(
  `${FLASK_API_BASE_URL}${endpoint}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: normalizedEmail,
        password,
      }),
    }
  )

  const result = await response.json()

  if (!response.ok || !result.success) {
    throw new Error(
      result.error || 'Login failed'
    )
  }

  sessionStorage.setItem('access_token',
    result.token
  )
  sessionStorage.setItem('user_id',
  String(
    role === 'teacher'
      ? result.teacher_id
      : result.student_id
  )
)

sessionStorage.setItem('user_name',
  result.name
)

sessionStorage.setItem('user_role',
  role
)

  return {
    user: {
      id: String(
        role === 'teacher'
          ? result.teacher_id
          : result.student_id
      ),
      name: result.name,
      email: normalizedEmail,
      role,
    },
    token: result.token,
  }
},
register: async (values: {
  name: string
  email: string
  password: string
  role: 'student' | 'teacher'
}) => {
  const endpoint =
    values.role === 'teacher'
      ? '/teacher/register'
      : '/register'

  const response = await fetch(
  `${FLASK_API_BASE_URL}${endpoint}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
  // No USN field exists in the register form yet -- the backend
  // assigns a real, unique USN when none is supplied.
  name: values.name,
  email: values.email,
  password: values.password,
  department: 'CSE',
  section: 'A',
  semester: 1,
}),
    },
  )

  const result = await response.json()

  if (!response.ok || !result.success) {
    throw new Error(
      result.error || 'Registration failed',
    )
  }

  return result
},
}

// ----------------------------------------------------------------------------
// CLASSES     GET /classes · POST /classes · PATCH /classes/:id/start · PATCH /classes/:id/end
// ----------------------------------------------------------------------------
export const classesApi = {
  list: async (): Promise<ClassSession[]> => {
  const token = sessionStorage.getItem('access_token')
  const role = sessionStorage.getItem('user_role')

  if (!token) {
    throw new Error('Please login again.')
  }

  // Teachers and students have separate "my classes" endpoints —
  // /my-classes is student-enrollment-scoped, so a teacher must use
  // /teacher/classrooms (creator-scoped) instead.
  const endpoint =
    role === 'teacher'
      ? '/teacher/classrooms'
      : '/my-classes'

  const response = await fetch(
    `${FLASK_API_BASE_URL}${endpoint}`,
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  )

  const result = await response.json()

  if (!response.ok || !result.success) {
    throw new Error(
      result.error || 'Unable to fetch classes',
    )
  }

  const rows = role === 'teacher' ? result.classrooms : result.classes

  return rows.map((c: any) => ({
    id: String(c.class_id),
    title: c.classroom_name ?? c.class_name,
    subject: c.subject,
    teacherId: '',
    teacherName: '',
    scheduledStart: c.start_time ?? new Date().toISOString(),
    scheduledEnd: c.end_time ?? new Date().toISOString(),
    // Real status computed server-side from the classroom's latest
    // session: no session yet -> scheduled, session still open -> live,
    // session ended -> completed. Previously this was hard-coded to
    // 'live' for every class regardless of real state.
    status: (c.status ?? 'scheduled') as ClassSession['status'],
    studentsEnrolled: c.students_enrolled ?? 0,
    studentsPresent: c.students_present ?? 0,
    avgEngagement: c.avg_engagement ?? undefined,
    coverColor: '#6366f1',
    recordingAvailable: c.status === 'completed',
  }))
},

join: async (classCode: string) => {
  const token = sessionStorage.getItem('access_token')

  if (!token) {
    throw new Error('Please login again.')
  }

  const response = await fetch(
    `${FLASK_API_BASE_URL}/join-class`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        class_code: classCode,
      }),
    },
  )

  const result = await response.json()

  if (!response.ok || !result.success) {
    throw new Error(
      result.error || 'Unable to join classroom',
    )
  }

  return result
},

get: (id: string) =>
  simulateNetwork<ClassSession | undefined>(
    getClassesStore().find((c) => c.id === id)
  ),
  create: async (input: {
  title: string
  subject: string
  scheduledStart: string
  startNow: boolean
}): Promise<ClassSession> => {
  const token = sessionStorage.getItem('access_token')

  if (!token) {
    throw new Error('Please login again.')
  }

  const response = await fetch(
  `${FLASK_API_BASE_URL}/teacher/create-classroom`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        classroom_name: input.title,
        subject: input.subject,
        semester: 1,
        section: 'A',
      }),
    },
  )

  const result = await response.json()

  if (!response.ok || !result.success) {
    throw new Error(
      result.error || 'Unable to create classroom',
    )
  }

  const classId = String(result.class_id)

  const newClass: ClassSession = {
    id: classId,
    title: input.title,
    subject: input.subject,
    teacherId: '',
    teacherName: '',
    scheduledStart: input.scheduledStart,
    scheduledEnd: input.scheduledStart,
    status: input.startNow ? 'live' : 'scheduled',
    studentsEnrolled: 0,
    studentsPresent: 0,
    avgEngagement: 0,
    coverColor: '#6366f1',
  }

  if (input.startNow) {
    const startResponse = await fetch(
      `http://127.0.0.1:5000/teacher/start-session/${classId}`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    )

    const startResult = await startResponse.json()

    if (!startResponse.ok || !startResult.success) {
      throw new Error(
        startResult.error || 'Unable to start class session',
      )
    }
  }

  return newClass
},
  start: async (id: string) => {
  const token = sessionStorage.getItem('access_token')

  if (!token) {
    throw new Error('Authentication token missing. Please login again.')
  }

  // Starts the EXISTING class's session. This previously called
  // /teacher/create-classroom, which ignored `id` entirely and created a
  // brand new (empty) classroom every time "Start class" was clicked.
  const response = await fetch(
    `${FLASK_API_BASE_URL}/teacher/start-session/${id}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    },
  )

  const result = await response.json()

  if (!response.ok || !result.success) {
    throw new Error(
      result.error || 'Unable to start class session',
    )
  }

  // Keep the legacy mock/localStorage class list (still used by
  // classesApi.get) in sync too.
  return startClassInStore(id)
},
  end: async (id: string) => {
  const token = sessionStorage.getItem('access_token')

  if (!token) {
    throw new Error('Authentication token missing. Please login again.')
  }

  const response = await fetch(
    `${FLASK_API_BASE_URL}/teacher/end-session/${id}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    },
  )

  const result = await response.json()

  if (!response.ok || !result.success) {
    throw new Error(
      result.error || 'Unable to end class session',
    )
  }

  // Keep existing frontend class state in sync.
  return endClassInStore(id)
},
}

// ----------------------------------------------------------------------------
// MONITORING  GET /classes/:id/live-students · WS /ws/classes/:id/engagement
// ----------------------------------------------------------------------------
export const monitoringApi = {
  // classId scopes the result to one class's current live session so a
  // teacher watching class A never sees class B's (or another teacher's)
  // students, and results never linger after a session ends. Omitting it
  // returns an empty list rather than falling back to global state.
  liveStudents: async (classId?: string) => {
    const query = classId ? `?class_id=${encodeURIComponent(classId)}` : ''

    const response = await fetch(
      `${API_BASE_URL}/live-monitor${query}`,
      {
        cache: 'no-store',
      },
    )

    const result = await response.json()

    if (!response.ok || !result.success) {
      throw new Error(
        result.error || 'Unable to fetch live monitoring data',
      )
    }

    const students = Array.isArray(result.data)
      ? result.data
      : []

    // Convert the REAL backend AI result into
    // the exact structure used by the teacher dashboard.
    return students.map((student: any) => ({
      // Coerced to string: the WebSocket AI-result path (real student_id
      // read from localStorage) is always a string, and this studentId is
      // used as a merge/dedup key against that path on the teacher side.
      studentId: String(
        student.studentId ??
        student.id ??
        'unknown',
      ),

      studentName:
        student.studentName ??
        student.name ??
        'Student',

      currentEmotion:
        student.currentEmotion ??
        student.emotion ??
        'neutral',

      currentEngagement: Number(
        student.currentEngagement ??
        student.engagement_score ??
        student.engagement ??
        0,
      ),

      authenticated:
        student.authenticated ?? true,

      cognitiveState:
        student.cognitiveState ??
        'focused',

      activeAlert:
        student.activeAlert ??
        undefined,

      history:
        Array.isArray(student.history)
          ? student.history
          : [
              Number(
                student.currentEngagement ??
                student.engagement_score ??
                0,
              ),
            ],

      micOn:
        student.micOn ?? false,

      cameraOn:
        student.cameraOn ?? true,

      // ==========================================================
      // REAL AI DATA
      // ==========================================================

      blinkCount: Number(
        student.blinkCount ??
        student.blink_count ??
        0,
      ),

      headPose:
        student.headPose ??
        student.head_pose ??
        'Forward',

      gaze:
        student.gaze ??
        'Center',

      phoneDetected:
        Boolean(
          student.phoneDetected ??
          student.phone_detected ??
          false,
        ),

      personCount: Number(
        student.personCount ??
        student.person_count ??
        1,
      ),

      engagementStatus:
        student.engagementStatus ??
        student.engagement_status ??
        undefined,
    }))
  },

  alerts: () =>
    simulateNetwork<AIAlert[]>(
      generateAlerts(24),
    ),
}

// ----------------------------------------------------------------------------
// ATTENDANCE  GET /teacher/attendance · GET /student/attendance
// ----------------------------------------------------------------------------
export const attendanceApi = {
  list: async (): Promise<AttendanceRecord[]> => {
    const token = sessionStorage.getItem('access_token')
    const role = sessionStorage.getItem('user_role')

    if (!token) {
      throw new Error('Please login again.')
    }

    const endpoint =
      role === 'teacher' ? '/teacher/attendance' : '/student/attendance'

    const response = await fetch(`${FLASK_API_BASE_URL}${endpoint}`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${token}` },
    })

    const result = await response.json()

    if (!response.ok || !result.success) {
      throw new Error(result.error || 'Unable to fetch attendance')
    }

    return (result.attendance ?? []).map((r: any) => ({
      id: r.id,
      studentId: String(r.studentId),
      studentName: r.studentName ?? '',
      classId: String(r.classId),
      className: r.className,
      date: r.date ?? new Date().toISOString(),
      status: r.status,
      joinTime: r.startTime ?? undefined,
      leaveTime: r.endTime ?? undefined,
      engagementAvg: r.engagementAvg ?? undefined,
    }))
  },
}

// ----------------------------------------------------------------------------
// CLASS HISTORY   GET /teacher/classroom/:id/history · GET /history/class/:id
// ----------------------------------------------------------------------------
export const historyApi = {
  // Teacher: every student who joined the class's most recent session,
  // with their real per-session summary + full snapshot timeline.
  teacherClassReport: async (classId: string) => {
    const token = sessionStorage.getItem('access_token')

    if (!token) {
      throw new Error('Please login again.')
    }

    const response = await fetch(
      `${FLASK_API_BASE_URL}/teacher/classroom/${classId}/history`,
      { headers: { Authorization: `Bearer ${token}` } },
    )

    const result = await response.json()

    if (!response.ok || !result.success) {
      throw new Error(result.error || 'Unable to fetch class report')
    }

    return result as {
      class: {
        class_id: number
        class_name: string
        subject: string
        session_id: number | null
        start_time: string | null
        end_time: string | null
        is_active?: boolean
      }
      students: Array<{
        studentId: number
        studentName: string
        usn: string | null
        attendanceStatus: 'present' | 'absent' | 'unknown'
        averageEngagement: number
        finalEngagement: number
        minEngagement: number
        maxEngagement: number
        sampleCount: number
        phoneDetections: number
        multiplePersonDetections: number
        lookingAwayCount: number
        attentionDropCount: number
        totalAlerts: number
        blinkCount: number
        snapshots: Array<{
          timestamp: string
          engagementScore: number
          emotion: string
          blinkCount: number
          headPose: string
          gaze: string
          phoneDetected: boolean
          multiplePerson: boolean
          engagementStatus: string
        }>
      }>
    }
  },

  // Student: their OWN history for this class only -- the backend derives
  // the student from the auth token, never from a client-supplied id.
  studentClassReport: async (classId: string) => {
    const token = sessionStorage.getItem('access_token')

    if (!token) {
      throw new Error('Please login again.')
    }

    const response = await fetch(
      `${FLASK_API_BASE_URL}/history/class/${classId}`,
      { headers: { Authorization: `Bearer ${token}` } },
    )

    const result = await response.json()

    if (!response.ok || !result.success) {
      throw new Error(result.error || 'Unable to fetch class report')
    }

    return result.history as {
      studentId: number
      studentName: string
      usn: string | null
      classId: number
      className: string
      subject: string
      sessionId: number
      startTime: string | null
      endTime: string | null
      attendanceStatus: 'present' | 'absent' | 'unknown'
      lookingAwayCount: number
      attentionDropCount: number
      totalAlerts: number
      blinkCount: number
      averageEngagement: number
      finalEngagement: number
      minEngagement: number
      maxEngagement: number
      sampleCount: number
      phoneDetections: number
      multiplePersonDetections: number
      snapshots: Array<{
        timestamp: string
        engagementScore: number
        emotion: string
        blinkCount: number
        headPose: string
        gaze: string
        phoneDetected: boolean
        multiplePerson: boolean
        engagementStatus: string
      }>
    } | null
  },
}

// ----------------------------------------------------------------------------
// REPORTS     GET /reports/engagement-trend · GET /reports/behavior-breakdown
// ----------------------------------------------------------------------------
export const reportsApi = {
  engagementTrend: () => simulateNetwork<EngagementTrendPoint[]>(generateEngagementTrend(14)),
  behaviorBreakdown: () => simulateNetwork(behaviorBreakdown),
}

// ----------------------------------------------------------------------------
// NOTIFICATIONS  GET /notifications · POST /notifications/:id/read
// ----------------------------------------------------------------------------
export const notificationsApi = {
  list: () => simulateNetwork<AppNotification[]>(generateNotifications(15)),
}

// ----------------------------------------------------------------------------
// TESTS       GET /tests · POST /tests · POST /tests/:id/submit
// ----------------------------------------------------------------------------
export const testsApi = {
  list: () => simulateNetwork<Test[]>(generateTests()),
}
