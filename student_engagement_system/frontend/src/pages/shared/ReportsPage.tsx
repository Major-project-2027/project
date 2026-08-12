import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileDown, FileText } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Tabs } from '@/components/ui/Tabs'
import { Button } from '@/components/ui/Button'
import { EngagementTrendChart } from '@/components/charts/EngagementTrendChart'
import { AttendanceBarChart } from '@/components/charts/AttendanceBarChart'
import { BehaviorPieChart } from '@/components/charts/BehaviorPieChart'
import { reportsApi } from '@/services/api/endpoints'
import type { UserRole } from '@/types/domain'

type Period = 'daily' | 'weekly' | 'monthly'
type Scope = 'class' | 'student'

export function ReportsPage({ role }: { role: UserRole }) {
  const [period, setPeriod] = useState<Period>('weekly')
  const [scope, setScope] = useState<Scope>('class')
  const trendQuery = useQuery({ queryKey: ['engagement-trend'], queryFn: reportsApi.engagementTrend })
  const breakdownQuery = useQuery({ queryKey: ['behavior-breakdown'], queryFn: reportsApi.behaviorBreakdown })

  return (
    <AppShell role={role} title="Reports">
      <div className="space-y-6">
        <Card>
          <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-center">
            <div className="flex flex-wrap items-center gap-3">
              <Tabs active={period} onChange={setPeriod} tabs={[{ value: 'daily', label: 'Daily' }, { value: 'weekly', label: 'Weekly' }, { value: 'monthly', label: 'Monthly' }]} />
              {role === 'teacher' && (
                <Tabs active={scope} onChange={setScope} tabs={[{ value: 'class', label: 'Class' }, { value: 'student', label: 'Student' }]} />
              )}
            </div>
            <Button size="sm" variant="outline" className="sm:ml-auto"><FileDown className="h-4 w-4" />Download PDF</Button>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-textmuted-light dark:text-textmuted-dark">
              Showing {period} {scope === 'student' ? 'per-student' : 'class-level'} engagement, attendance, and behavior analysis.
            </p>
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader className="pb-3"><CardTitle>Engagement trend</CardTitle><CardDescription>Rolling average, {period}</CardDescription></CardHeader>
            <CardContent className="pt-0"><EngagementTrendChart data={trendQuery.data ?? []} /></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3"><CardTitle>Attendance rate</CardTitle><CardDescription>Percentage present per session</CardDescription></CardHeader>
            <CardContent className="pt-0"><AttendanceBarChart data={trendQuery.data ?? []} /></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3"><CardTitle>Behaviour analysis</CardTitle><CardDescription>Cognitive state distribution</CardDescription></CardHeader>
            <CardContent className="pt-0"><BehaviorPieChart data={breakdownQuery.data ?? []} /></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3"><CardTitle>Report archive</CardTitle><CardDescription>Previously generated reports</CardDescription></CardHeader>
            <CardContent className="pt-3 space-y-2">
              {['Weekly Report — Jul 21–27', 'Weekly Report — Jul 14–20', 'Monthly Report — June 2026'].map((name) => (
                <div key={name} className="flex items-center justify-between rounded-lg border border-border-light p-2.5 text-sm dark:border-border-dark">
                  <span className="flex items-center gap-2 text-text-light dark:text-text-dark"><FileText className="h-4 w-4 text-focus-500" />{name}</span>
                  <Button variant="ghost" size="sm">Download</Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  )
}
