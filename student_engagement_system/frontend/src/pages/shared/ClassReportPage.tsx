import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Users, Bell, BrainCircuit } from 'lucide-react'

import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { Button } from '@/components/ui/Button'
import { EngagementTrendChart } from '@/components/charts/EngagementTrendChart'
import { historyApi } from '@/services/api/endpoints'
import { formatDateTime, formatTime, engagementTone, cognitiveStateText, cognitiveStateTone } from '@/lib/utils'
import type { UserRole } from '@/types/domain'

type Snapshot = {
  timestamp: string
  engagementScore: number
  emotion: string
  blinkCount: number
  headPose: string
  gaze: string
  phoneDetected: boolean
  multiplePerson: boolean
  engagementStatus: string
}

// Session-level, rule-based Cognitive State summary -- see
// backend/services/cognitive_state_service.py. Only ever populated on the
// TEACHER'S report (teacherClassReport) -- deliberately omitted from the
// student's own class report (studentClassReport never returns it), per
// the product decision that this is a teacher/research summary, not
// something shown to the student. That's why this is optional here:
// StudentReportDetail below only renders the cognitive-state section when
// it is actually present.
type CognitiveStateSummary = {
  status: 'ok' | 'insufficient_data' | 'not_available'
  state: 'focused' | 'neutral' | 'distracted' | 'drowsy' | null
  focusedPercentage: number | null
  neutralPercentage: number | null
  distractedPercentage: number | null
  drowsyEpisodeCount: number
  reason: string | null
}

type StudentSummary = {
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
  cognitiveState?: CognitiveStateSummary
  snapshots: Snapshot[]
}

const ATTENDANCE_VARIANT = {
  present: 'engaged',
  absent: 'critical',
  unknown: 'neutral',
} as const

function StatPill({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
      <Icon className="h-4 w-4 text-textmuted-light dark:text-textmuted-dark" />
      <div>
        <p className="text-sm font-semibold text-text-light dark:text-text-dark">{value}</p>
        <p className="text-[11px] text-textmuted-light dark:text-textmuted-dark">{label}</p>
      </div>
    </div>
  )
}

function StudentReportDetail({ student }: { student: StudentSummary }) {
  const trend = student.snapshots.map((s) => ({
    label: formatTime(s.timestamp),
    avgEngagement: Math.round(s.engagementScore ?? 0),
    attendanceRate: 0,
  }))

  return (
    <div className="space-y-4">
      {/* Only the two summary cards the report is scoped to now --
          finalEngagement/minEngagement/maxEngagement/sampleCount/
          blinkCount/phoneDetections/lookingAwayCount/
          multiplePersonDetections/attentionDropCount are still returned
          by the backend (StudentSummary/Snapshot below) and still power
          the graph and any other consumer -- this component just no
          longer renders a card for each of them. */}
      <div className="grid grid-cols-2 gap-3 sm:max-w-xs">
        <StatPill icon={Users} label="Avg. engagement" value={`${student.averageEngagement}%`} />
        <StatPill icon={Bell} label="Total alerts" value={student.totalAlerts} />
      </div>

      {student.cognitiveState && (
        <div className="rounded-xl border border-border-light p-3 dark:border-border-dark">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-textmuted-light dark:text-textmuted-dark">
            <BrainCircuit className="h-3.5 w-3.5" />
            Cognitive state
          </p>

          {student.cognitiveState.status === 'ok' ? (
            <>
              <Badge variant={cognitiveStateTone(student.cognitiveState.state)}>
                {cognitiveStateText(student.cognitiveState.state)}
              </Badge>

              {student.cognitiveState.focusedPercentage !== null && (
                <div className="mt-2 space-y-1 text-xs text-textmuted-light dark:text-textmuted-dark">
                  <p>Focused: {student.cognitiveState.focusedPercentage}%</p>
                  <p>Neutral: {student.cognitiveState.neutralPercentage}%</p>
                  <p>Distracted: {student.cognitiveState.distractedPercentage}%</p>
                </div>
              )}

              {student.cognitiveState.state === 'drowsy' && (
                <p className="mt-1 text-xs text-textmuted-light dark:text-textmuted-dark">
                  {student.cognitiveState.drowsyEpisodeCount} confirmed drowsiness episode
                  {student.cognitiveState.drowsyEpisodeCount === 1 ? '' : 's'} this session.
                </p>
              )}
            </>
          ) : (
            <p className="text-xs text-textmuted-light dark:text-textmuted-dark">
              {student.cognitiveState.reason ??
                (student.cognitiveState.status === 'not_available'
                  ? 'Not yet available.'
                  : 'Insufficient data for this session.')}
            </p>
          )}
        </div>
      )}

      {trend.length > 0 ? (
        <div>
          <p className="mb-2 text-xs font-medium text-textmuted-light dark:text-textmuted-dark">Engagement over the session</p>
          <EngagementTrendChart data={trend} />
        </div>
      ) : (
        <EmptyState icon={Users} title="No timeline data" description="No monitoring snapshots were recorded." />
      )}
    </div>
  )
}

export function ClassReportPage({ role }: { role: UserRole }) {
  const { classId } = useParams()
  const navigate = useNavigate()
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null)

  const teacherQuery = useQuery({
    queryKey: ['class-report', 'teacher', classId],
    queryFn: () => historyApi.teacherClassReport(classId ?? ''),
    enabled: role === 'teacher' && Boolean(classId),
  })

  const studentQuery = useQuery({
    queryKey: ['class-report', 'student', classId],
    queryFn: () => historyApi.studentClassReport(classId ?? ''),
    enabled: role === 'student' && Boolean(classId),
  })

  const isLoading = role === 'teacher' ? teacherQuery.isLoading : studentQuery.isLoading
  const isError = role === 'teacher' ? teacherQuery.isError : studentQuery.isError

  const classInfo = role === 'teacher'
    ? teacherQuery.data?.class
    : studentQuery.data
      ? {
          class_id: studentQuery.data.classId,
          class_name: studentQuery.data.className,
          subject: studentQuery.data.subject,
          start_time: studentQuery.data.startTime,
          end_time: studentQuery.data.endTime,
        }
      : undefined

  const students = teacherQuery.data?.students ?? []
  const selectedStudent = students.find((s) => s.studentId === selectedStudentId) ?? null

  return (
    <AppShell role={role} title="Class report">
      <div className="space-y-4">
        <Button variant="outline" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>

        <Card>
          <CardHeader className="flex-col items-stretch gap-1 sm:flex-row sm:items-center">
            <div>
              <CardTitle>{classInfo?.class_name ?? 'Class report'}</CardTitle>
              <CardDescription>
                {classInfo?.subject}
                {classInfo?.start_time && ` · ${formatDateTime(classInfo.start_time)}`}
                {classInfo?.end_time && ` – ${formatTime(classInfo.end_time)}`}
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="pt-3">
            {isLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}
              </div>
            ) : isError ? (
              <ErrorState onRetry={() => (role === 'teacher' ? teacherQuery.refetch() : studentQuery.refetch())} />
            ) : role === 'teacher' ? (
              students.length === 0 ? (
                <EmptyState icon={Users} title="No students attended this class" description="No monitoring data was recorded for this session." />
              ) : (
                <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
                  <ul className="space-y-1">
                    {students.map((s) => (
                      <li key={s.studentId}>
                        <button
                          onClick={() => setSelectedStudentId(s.studentId)}
                          className={`flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition-colors ${
                            selectedStudentId === s.studentId
                              ? 'bg-focus-500/10'
                              : 'hover:bg-black/5 dark:hover:bg-white/5'
                          }`}
                        >
                          <Avatar name={s.studentName} size={30} />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-text-light dark:text-text-dark">{s.studentName}</p>
                            <p className="truncate text-xs text-textmuted-light dark:text-textmuted-dark">{s.usn ?? '—'}</p>
                          </div>
                          <div className="flex shrink-0 flex-col items-end gap-1">
                            <Badge variant={ATTENDANCE_VARIANT[s.attendanceStatus]}>{s.attendanceStatus}</Badge>
                            {s.cognitiveState?.status === 'ok' && (
                              <Badge variant={cognitiveStateTone(s.cognitiveState.state)}>
                                {cognitiveStateText(s.cognitiveState.state)}
                              </Badge>
                            )}
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>

                  <div>
                    {selectedStudent ? (
                      <div className="space-y-4">
                        <div className="flex items-center gap-3">
                          <Avatar name={selectedStudent.studentName} size={36} />
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-text-light dark:text-text-dark">{selectedStudent.studentName}</p>
                            <p className="truncate text-xs text-textmuted-light dark:text-textmuted-dark">{selectedStudent.usn ?? '—'}</p>
                          </div>
                          <Badge variant={ATTENDANCE_VARIANT[selectedStudent.attendanceStatus]}>{selectedStudent.attendanceStatus}</Badge>
                        </div>
                        <StudentReportDetail student={selectedStudent} />
                      </div>
                    ) : (
                      <EmptyState icon={Users} title="Select a student" description="Click a student on the left to see their session details." />
                    )}
                  </div>
                </div>
              )
            ) : studentQuery.data ? (
              <div className="space-y-3">
                <p className="text-sm font-medium text-text-light dark:text-text-dark">
                  {studentQuery.data.studentName}
                </p>
                <div className="flex items-center gap-2">
                  <Badge variant={ATTENDANCE_VARIANT[studentQuery.data.attendanceStatus]}>
                    {studentQuery.data.attendanceStatus}
                  </Badge>
                  <span
                    className={`text-xs font-medium ${
                      engagementTone(studentQuery.data.averageEngagement) === 'engaged'
                        ? 'text-engaged-600 dark:text-engaged-400'
                        : engagementTone(studentQuery.data.averageEngagement) === 'attention'
                          ? 'text-attention-600 dark:text-attention-400'
                          : 'text-critical-600 dark:text-critical-400'
                    }`}
                  >
                    {studentQuery.data.averageEngagement}% average engagement
                  </span>
                </div>
                <StudentReportDetail
                  student={{
                    studentId: studentQuery.data.studentId,
                    studentName: studentQuery.data.studentName,
                    usn: studentQuery.data.usn,
                    attendanceStatus: studentQuery.data.attendanceStatus,
                    averageEngagement: studentQuery.data.averageEngagement,
                    finalEngagement: studentQuery.data.finalEngagement,
                    minEngagement: studentQuery.data.minEngagement,
                    maxEngagement: studentQuery.data.maxEngagement,
                    sampleCount: studentQuery.data.sampleCount,
                    phoneDetections: studentQuery.data.phoneDetections,
                    multiplePersonDetections: studentQuery.data.multiplePersonDetections,
                    lookingAwayCount: studentQuery.data.lookingAwayCount,
                    attentionDropCount: studentQuery.data.attentionDropCount,
                    totalAlerts: studentQuery.data.totalAlerts,
                    blinkCount: studentQuery.data.blinkCount,
                    snapshots: studentQuery.data.snapshots,
                  }}
                />
              </div>
            ) : (
              <EmptyState icon={Users} title="No monitoring data available" description="This class doesn't have any recorded monitoring data for you yet." />
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
