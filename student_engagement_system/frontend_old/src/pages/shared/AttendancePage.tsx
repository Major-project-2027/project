import { useQuery } from '@tanstack/react-query'
import { Download, ClipboardList } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { attendanceApi } from '@/services/api/endpoints'
import { Avatar } from '@/components/ui/Avatar'
import type { UserRole } from '@/types/domain'

const STATUS_VARIANT = {
  present: 'engaged',
  late: 'attention',
  absent: 'critical',
  left_early: 'attention',
} as const

export function AttendancePage({ role }: { role: UserRole }) {
  const attendanceQuery = useQuery({ queryKey: ['attendance'], queryFn: attendanceApi.list })
  const records = attendanceQuery.data ?? []
  const presentCount = records.filter((r) => r.status === 'present').length

  return (
    <AppShell role={role} title="Attendance">
      <Card>
        <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <div>
            <CardTitle>Attendance records</CardTitle>
            <CardDescription>{role === 'teacher' ? 'Machine Learning — Unit 3' : 'Your attendance across all classes'}</CardDescription>
          </div>
          <Button variant="outline" size="sm" className="sm:ml-auto"><Download className="h-4 w-4" />Export CSV</Button>
        </CardHeader>
        <CardContent className="pt-3">
          <div className="mb-4 flex flex-wrap gap-3 text-sm">
            <span className="rounded-full bg-engaged-500/10 px-3 py-1 text-engaged-600 dark:text-engaged-400">{presentCount} present</span>
            <span className="rounded-full bg-critical-500/10 px-3 py-1 text-critical-600 dark:text-critical-400">{records.filter((r) => r.status === 'absent').length} absent</span>
            <span className="rounded-full bg-attention-500/10 px-3 py-1 text-attention-600 dark:text-attention-400">{records.filter((r) => r.status === 'late').length} late</span>
          </div>

          {attendanceQuery.isLoading ? (
            <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : records.length === 0 ? (
            <EmptyState icon={ClipboardList} title="No attendance yet" description="Records appear once a class session has taken place." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border-light text-xs text-textmuted-light dark:border-border-dark dark:text-textmuted-dark">
                    {role === 'teacher' && <th className="pb-2 font-medium">Student</th>}
                    <th className="pb-2 font-medium">Class</th>
                    <th className="pb-2 font-medium">Join / Leave</th>
                    <th className="pb-2 font-medium">Engagement avg.</th>
                    <th className="pb-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => (
                    <tr key={r.id} className="border-b border-border-light last:border-0 dark:border-border-dark">
                      {role === 'teacher' && (
                        <td className="py-2.5">
                          <div className="flex items-center gap-2">
                            <Avatar name={r.studentName} size={26} />
                            <span className="text-text-light dark:text-text-dark">{r.studentName}</span>
                          </div>
                        </td>
                      )}
                      <td className="py-2.5 text-textmuted-light dark:text-textmuted-dark">{r.className}</td>
                      <td className="py-2.5 font-mono text-xs text-textmuted-light dark:text-textmuted-dark">{r.joinTime} – {r.leaveTime}</td>
                      <td className="py-2.5 text-textmuted-light dark:text-textmuted-dark">{r.engagementAvg}%</td>
                      <td className="py-2.5"><Badge variant={STATUS_VARIANT[r.status]}>{r.status.replace('_', ' ')}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </AppShell>
  )
}
