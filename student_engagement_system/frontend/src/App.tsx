import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { ProtectedRoute } from '@/components/common/ProtectedRoute'
import { FocusPulse } from '@/components/monitoring/ConfidenceRing'

// Lazy-loaded route-level code splitting keeps the initial bundle small as
// the page count grows — each route ships its own chunk on first visit.
const LandingPage = lazy(() => import('@/pages/shared/LandingPage').then((m) => ({ default: m.LandingPage })))
const LoginPage = lazy(() => import('@/pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage').then((m) => ({ default: m.RegisterPage })))
const FaceRegistrationPage = lazy(() => import('@/pages/auth/FaceRegistrationPage').then((m) => ({ default: m.FaceRegistrationPage })))
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })))

const TeacherDashboardPage = lazy(() => import('@/pages/teacher/TeacherDashboardPage').then((m) => ({ default: m.TeacherDashboardPage })))
const TeacherClassesPage = lazy(() => import('@/pages/teacher/TeacherClassesPage').then((m) => ({ default: m.TeacherClassesPage })))
const AnalyticsPage = lazy(() => import('@/pages/teacher/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })))
const FutureEngagementPredictionPage = lazy(() => import('@/pages/teacher/FutureEngagementPredictionPage').then((m) => ({ default: m.FutureEngagementPredictionPage })))
const TeacherTestsPage = lazy(() => import('@/pages/test/TeacherTestsPage').then((m) => ({ default: m.TeacherTestsPage })))
const TeacherTestMonitorPage = lazy(() => import('@/pages/test/TeacherTestMonitorPage').then((m) => ({ default: m.TeacherTestMonitorPage })))

const StudentDashboardPage = lazy(() => import('@/pages/student/StudentDashboardPage').then((m) => ({ default: m.StudentDashboardPage })))
const StudentClassesPage = lazy(() => import('@/pages/student/StudentClassesPage').then((m) => ({ default: m.StudentClassesPage })))
const StudentTestsPage = lazy(() => import('@/pages/test/StudentTestsPage').then((m) => ({ default: m.StudentTestsPage })))
const StudentTestTakingPage = lazy(() => import('@/pages/test/StudentTestTakingPage').then((m) => ({ default: m.StudentTestTakingPage })))

const AdminDashboardPage = lazy(() => import('@/pages/admin/AdminDashboardPage').then((m) => ({ default: m.AdminDashboardPage })))

const AttendancePage = lazy(() => import('@/pages/shared/AttendancePage').then((m) => ({ default: m.AttendancePage })))
const ClassReportPage = lazy(() => import('@/pages/shared/ClassReportPage').then((m) => ({ default: m.ClassReportPage })))
const ReportsPage = lazy(() => import('@/pages/shared/ReportsPage').then((m) => ({ default: m.ReportsPage })))
const NotificationsPage = lazy(() => import('@/pages/shared/NotificationsPage').then((m) => ({ default: m.NotificationsPage })))
const ProfilePage = lazy(() => import('@/pages/shared/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const SettingsPage = lazy(() => import('@/pages/shared/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const HelpPage = lazy(() => import('@/pages/shared/HelpPage').then((m) => ({ default: m.HelpPage })))
const SupportPage = lazy(() => import('@/pages/shared/SupportPage').then((m) => ({ default: m.SupportPage })))
const AboutPage = lazy(() => import('@/pages/shared/AboutPage').then((m) => ({ default: m.AboutPage })))

const TeacherLiveClassroomPage = lazy(() => import('@/pages/live-classroom/TeacherLiveClassroomPage').then((m) => ({ default: m.TeacherLiveClassroomPage })))
const StudentLiveClassroomPage = lazy(() => import('@/pages/live-classroom/StudentLiveClassroomPage').then((m) => ({ default: m.StudentLiveClassroomPage })))
const PreJoinLobbyPage = lazy(() => import('@/pages/live-classroom/PreJoinLobbyPage').then((m) => ({ default: m.PreJoinLobbyPage })))
const FaceVerificationPage = lazy(() => import('@/pages/live-classroom/FaceVerificationPage').then((m) => ({ default: m.FaceVerificationPage })))
const ResultPage = lazy(() => import('@/pages/test/ResultPage').then((m) => ({ default: m.ResultPage })))

const NotFoundPage = lazy(() => import('@/pages/error/NotFoundPage').then((m) => ({ default: m.NotFoundPage })))

function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-light dark:bg-bg-dark">
      <FocusPulse />
    </div>
  )
}

function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* Public */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/register/face" element={<ProtectedRoute role="student"><FaceRegistrationPage /></ProtectedRoute>} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="/support" element={<SupportPage />} />
        <Route path="/about" element={<AboutPage />} />

        {/* Teacher */}
        <Route path="/teacher" element={<ProtectedRoute role="teacher"><TeacherDashboardPage /></ProtectedRoute>} />
        <Route path="/teacher/classes" element={<ProtectedRoute role="teacher"><TeacherClassesPage /></ProtectedRoute>} />
        <Route path="/teacher/attendance" element={<ProtectedRoute role="teacher"><AttendancePage role="teacher" /></ProtectedRoute>} />
        <Route path="/teacher/analytics" element={<ProtectedRoute role="teacher"><AnalyticsPage /></ProtectedRoute>} />
        <Route path="/teacher/future-engagement-prediction" element={<ProtectedRoute role="teacher"><FutureEngagementPredictionPage /></ProtectedRoute>} />
        <Route path="/teacher/tests" element={<ProtectedRoute role="teacher"><TeacherTestsPage /></ProtectedRoute>} />
        <Route path="/teacher/tests/:testId/monitor" element={<ProtectedRoute role="teacher"><TeacherTestMonitorPage /></ProtectedRoute>} />
        <Route path="/teacher/tests/:testId/results" element={<ProtectedRoute role="teacher"><ResultPage role="teacher" /></ProtectedRoute>} />
        <Route path="/teacher/reports" element={<ProtectedRoute role="teacher"><ReportsPage role="teacher" /></ProtectedRoute>} />
        <Route path="/teacher/notifications" element={<ProtectedRoute role="teacher"><NotificationsPage role="teacher" /></ProtectedRoute>} />
        <Route path="/teacher/settings" element={<ProtectedRoute role="teacher"><SettingsPage role="teacher" /></ProtectedRoute>} />
        <Route path="/teacher/profile" element={<ProtectedRoute role="teacher"><ProfilePage role="teacher" /></ProtectedRoute>} />
        <Route path="/teacher/live/:classId" element={<ProtectedRoute role="teacher"><TeacherLiveClassroomPage /></ProtectedRoute>} />
        <Route path="/teacher/lobby/:classId" element={<ProtectedRoute role="teacher"><PreJoinLobbyPage role="teacher" /></ProtectedRoute>} />
        <Route path="/teacher/classroom/:classId/report" element={<ProtectedRoute role="teacher"><ClassReportPage role="teacher" /></ProtectedRoute>} />

        {/* Student */}
        <Route path="/student" element={<ProtectedRoute role="student"><StudentDashboardPage /></ProtectedRoute>} />
        <Route path="/student/classes" element={<ProtectedRoute role="student"><StudentClassesPage /></ProtectedRoute>} />
        <Route path="/student/attendance" element={<ProtectedRoute role="student"><AttendancePage role="student" /></ProtectedRoute>} />
        <Route path="/student/tests" element={<ProtectedRoute role="student"><StudentTestsPage /></ProtectedRoute>} />
        <Route path="/student/tests/:testId/take" element={<ProtectedRoute role="student"><StudentTestTakingPage /></ProtectedRoute>} />
        <Route path="/student/tests/:testId/result" element={<ProtectedRoute role="student"><ResultPage role="student" /></ProtectedRoute>} />
        <Route path="/student/reports" element={<ProtectedRoute role="student"><ReportsPage role="student" /></ProtectedRoute>} />
        <Route path="/student/notifications" element={<ProtectedRoute role="student"><NotificationsPage role="student" /></ProtectedRoute>} />
        <Route path="/student/settings" element={<ProtectedRoute role="student"><SettingsPage role="student" /></ProtectedRoute>} />
        <Route path="/student/profile" element={<ProtectedRoute role="student"><ProfilePage role="student" /></ProtectedRoute>} />
        <Route path="/student/live/:classId" element={<ProtectedRoute role="student"><StudentLiveClassroomPage /></ProtectedRoute>} />
        <Route path="/student/lobby/:classId" element={<ProtectedRoute role="student"><PreJoinLobbyPage role="student" /></ProtectedRoute>} />
        <Route path="/student/verify/:classId" element={<ProtectedRoute role="student"><FaceVerificationPage /></ProtectedRoute>} />
        <Route path="/student/classroom/:classId/report" element={<ProtectedRoute role="student"><ClassReportPage role="student" /></ProtectedRoute>} />

        {/* Admin */}
        <Route path="/admin" element={<ProtectedRoute role="admin"><AdminDashboardPage /></ProtectedRoute>} />
        <Route path="/admin/teachers" element={<ProtectedRoute role="admin"><AdminDashboardPage /></ProtectedRoute>} />
        <Route path="/admin/students" element={<ProtectedRoute role="admin"><AdminDashboardPage /></ProtectedRoute>} />
        <Route path="/admin/system" element={<ProtectedRoute role="admin"><AdminDashboardPage /></ProtectedRoute>} />
        <Route path="/admin/reports" element={<ProtectedRoute role="admin"><ReportsPage role="admin" /></ProtectedRoute>} />

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}

export default App
