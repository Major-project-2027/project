import { API_BASE_URL, FLASK_API_BASE_URL, simulateNetwork } from './client'
import {
  generateLiveStudents, generateAlerts, generateAttendance,
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
  login: async (email: string, password: string) => {
  const normalizedEmail = email.toLowerCase().trim()

  const role = normalizedEmail.includes('teacher')
    ? 'teacher'
    : normalizedEmail.includes('student')
      ? 'student'
      : null

  if (!role) {
    throw new Error(
      "Demo login: use an email containing 'teacher' or 'student'."
    )
  }

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

  localStorage.setItem(
    'access_token',
    result.token
  )
  localStorage.setItem(
  'user_id',
  String(
    role === 'teacher'
      ? result.teacher_id
      : result.student_id
  )
)

localStorage.setItem(
  'user_name',
  result.name
)

localStorage.setItem(
  'user_role',
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
  usn: 'STUDENT001',
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
  const token = localStorage.getItem('access_token')

  if (!token) {
    throw new Error('Please login again.')
  }

  const response = await fetch(
    `${FLASK_API_BASE_URL}/my-classes`,
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

  return result.classes.map((c: any) => ({
    id: String(c.class_id),
    title: c.class_name,
    subject: c.subject,
    teacherId: '',
    teacherName: '',
    scheduledStart: new Date().toISOString(),
    scheduledEnd: new Date().toISOString(),
    status: 'live',
    studentsEnrolled: 0,
    studentsPresent: 0,
    avgEngagement: 0,
    coverColor: '#6366f1',
  }))
},

join: async (classCode: string) => {
  const token = localStorage.getItem('access_token')

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
  const token = localStorage.getItem('access_token')

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
  const token = localStorage.getItem('access_token')

  if (!token) {
    throw new Error('Authentication token missing. Please login again.')
  }

  const response = await fetch(
    `http://127.0.0.1:5000/teacher/create-classroom`,
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

  // Keep the existing frontend class state in sync.
  return startClassInStore(id)
},
  end: async (id: string) => {
  const token = localStorage.getItem('access_token')

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
  liveStudents: async () => {
    const response = await fetch(
      `${API_BASE_URL}/live-monitor`,
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
      studentId:
        student.studentId ??
        student.id ??
        'unknown',

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
// ATTENDANCE  GET /attendance?classId=&studentId=&date=
// ----------------------------------------------------------------------------
export const attendanceApi = {
    list: () => simulateNetwork<AttendanceRecord[]>(generateAttendance()),
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
