import { simulateNetwork } from './client'
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
  login: (email: string, _password: string) =>
    simulateNetwork<{ user: User; token: string }>(
      { user: email.includes('teacher') ? currentTeacher : currentStudent, token: 'mock-jwt-token' },
      600,
    ),
  register: (payload: { name: string; email: string; role: string }) =>
    simulateNetwork({ success: true, message: `Account created for ${payload.name}` }, 700),
  forgotPassword: (email: string) =>
    simulateNetwork({ success: true, message: `Reset link sent to ${email}` }, 600),
}

// ----------------------------------------------------------------------------
// CLASSES     GET /classes · POST /classes · PATCH /classes/:id/start · PATCH /classes/:id/end
// ----------------------------------------------------------------------------
export const classesApi = {
  list: () => simulateNetwork<ClassSession[]>(getClassesStore()),
  get: (id: string) => simulateNetwork<ClassSession | undefined>(getClassesStore().find((c) => c.id === id)),
  create: (input: { title: string; subject: string; scheduledStart: string; startNow: boolean }) =>
    simulateNetwork<ClassSession>(createClassInStore(input), 500),
  start: (id: string) => simulateNetwork<ClassSession | undefined>(startClassInStore(id), 400),
  end: (id: string) => simulateNetwork<ClassSession | undefined>(endClassInStore(id), 400),
}

// ----------------------------------------------------------------------------
// MONITORING  GET /classes/:id/live-students · WS /ws/classes/:id/engagement
// ----------------------------------------------------------------------------
export const monitoringApi = {
  liveStudents: () => simulateNetwork<StudentLiveState[]>(generateLiveStudents(16)),
  alerts: () => simulateNetwork<AIAlert[]>(generateAlerts(24)),
}

// ----------------------------------------------------------------------------
// ATTENDANCE  GET /attendance?classId=&studentId=&date=
// ----------------------------------------------------------------------------
export const attendanceApi = {
  list: () => simulateNetwork<AttendanceRecord[]>(generateAttendance(20)),
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
