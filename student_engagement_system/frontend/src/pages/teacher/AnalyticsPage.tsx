import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { EngagementTrendChart } from '@/components/charts/EngagementTrendChart'
import { BehaviorPieChart } from '@/components/charts/BehaviorPieChart'
import { AttendanceBarChart } from '@/components/charts/AttendanceBarChart'
import { reportsApi, monitoringApi } from '@/services/api/endpoints'
import { ConfidenceRing } from '@/components/monitoring/ConfidenceRing'
import { Avatar } from '@/components/ui/Avatar'
import { generateLiveStudents } from '@/mocks/data'

export function AnalyticsPage() {
  const trendQuery = useQuery({ queryKey: ['engagement-trend'], queryFn: reportsApi.engagementTrend })
  const breakdownQuery = useQuery({ queryKey: ['behavior-breakdown'], queryFn: reportsApi.behaviorBreakdown })
  useQuery({ queryKey: ['alerts'], queryFn: monitoringApi.alerts })
  const students = generateLiveStudents(8).sort((a, b) => a.currentEngagement - b.currentEngagement)

  return (
    <AppShell role="teacher" title="Analytics">
      <div className="space-y-6">
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3"><CardTitle>Engagement over time</CardTitle><CardDescription>All classes, last 14 days</CardDescription></CardHeader>
            <CardContent className="pt-0"><EngagementTrendChart data={trendQuery.data ?? []} /></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3"><CardTitle>Cognitive states</CardTitle></CardHeader>
            <CardContent className="pt-0"><BehaviorPieChart data={breakdownQuery.data ?? []} /></CardContent>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3"><CardTitle>Attendance vs engagement</CardTitle><CardDescription>Comparing consistency of presence and focus</CardDescription></CardHeader>
            <CardContent className="pt-0"><AttendanceBarChart data={trendQuery.data ?? []} /></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Students needing attention</CardTitle>
              <CardDescription>Lowest engagement this week</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 pt-0">
              {students.slice(0, 5).map((s) => (
                <div key={s.studentId} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Avatar name={s.studentName} size={30} />
                    <div>
                      <p className="text-sm font-medium text-text-light dark:text-text-dark">{s.studentName}</p>
                      <p className="text-xs capitalize text-textmuted-light dark:text-textmuted-dark">{s.cognitiveState}</p>
                    </div>
                  </div>
                  <ConfidenceRing value={s.currentEngagement} size={40} strokeWidth={4} />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
