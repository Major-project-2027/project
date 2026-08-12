import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, StopCircle, ShieldAlert } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Avatar } from '@/components/ui/Avatar'
import { generateLiveStudents } from '@/mocks/data'
import { ConfidenceRing } from '@/components/monitoring/ConfidenceRing'

export function TeacherTestMonitorPage() {
  const { testId } = useParams()
  const navigate = useNavigate()
  const [students] = useState(() => generateLiveStudents(20).map((s) => ({ ...s, integrityFlags: Math.random() > 0.75 ? Math.ceil(Math.random() * 3) : 0 })))
  const flagged = students.filter((s) => s.integrityFlags > 0)

  return (
    <AppShell role="teacher" title="Test Monitor">
      <div className="space-y-6">
        <Card>
          <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-center">
            <div>
              <CardTitle>Neural Networks — Mid Unit Quiz</CardTitle>
              <CardDescription>Test ID {testId} · {students.length} students in progress</CardDescription>
            </div>
            <Button variant="danger" size="sm" className="sm:ml-auto" onClick={() => navigate('/teacher/tests')}><StopCircle className="h-4 w-4" />End test</Button>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 pt-0 sm:grid-cols-4">
            <div className="rounded-lg bg-black/[0.03] p-3 dark:bg-white/[0.04]"><p className="text-xs text-textmuted-light dark:text-textmuted-dark">In progress</p><p className="font-display text-xl font-bold text-text-light dark:text-text-dark">{students.length - 2}</p></div>
            <div className="rounded-lg bg-black/[0.03] p-3 dark:bg-white/[0.04]"><p className="text-xs text-textmuted-light dark:text-textmuted-dark">Submitted</p><p className="font-display text-xl font-bold text-text-light dark:text-text-dark">2</p></div>
            <div className="rounded-lg bg-critical-500/10 p-3"><p className="text-xs text-critical-600 dark:text-critical-400">Integrity flags</p><p className="font-display text-xl font-bold text-critical-600 dark:text-critical-400">{flagged.length}</p></div>
            <div className="rounded-lg bg-black/[0.03] p-3 dark:bg-white/[0.04]"><p className="text-xs text-textmuted-light dark:text-textmuted-dark">Avg. time left</p><p className="font-display text-xl font-bold text-text-light dark:text-text-dark">14:32</p></div>
          </CardContent>
        </Card>

        {flagged.length > 0 && (
          <Card className="border-critical-500/30">
            <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-critical-600 dark:text-critical-400"><AlertTriangle className="h-4 w-4" />Integrity alerts</CardTitle></CardHeader>
            <CardContent className="space-y-2 pt-0">
              {flagged.map((s) => (
                <div key={s.studentId} className="flex items-center justify-between rounded-lg border border-critical-500/20 bg-critical-500/5 p-2.5">
                  <div className="flex items-center gap-2.5">
                    <Avatar name={s.studentName} size={30} />
                    <div>
                      <p className="text-sm font-medium text-text-light dark:text-text-dark">{s.studentName}</p>
                      <p className="text-xs text-textmuted-light dark:text-textmuted-dark">{s.activeAlert?.replace('_', ' ') ?? 'gaze deviation'} detected</p>
                    </div>
                  </div>
                  <Badge variant="critical">{s.integrityFlags} flag{s.integrityFlags > 1 ? 's' : ''}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-3"><CardTitle>Student proctoring grid</CardTitle><CardDescription>Live face auth + gaze status per student</CardDescription></CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 pt-0 sm:grid-cols-3 lg:grid-cols-4">
            {students.map((s) => (
              <div key={s.studentId} className="flex items-center gap-2.5 rounded-lg border border-border-light p-2.5 dark:border-border-dark">
                <Avatar name={s.studentName} size={34} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-text-light dark:text-text-dark">{s.studentName}</p>
                  <p className="flex items-center gap-1 text-[11px] text-textmuted-light dark:text-textmuted-dark">
                    {s.authenticated ? 'Verified' : <span className="flex items-center gap-1 text-critical-500"><ShieldAlert className="h-3 w-3" />Unverified</span>}
                  </p>
                </div>
                <ConfidenceRing value={s.currentEngagement} size={32} strokeWidth={3.5} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
