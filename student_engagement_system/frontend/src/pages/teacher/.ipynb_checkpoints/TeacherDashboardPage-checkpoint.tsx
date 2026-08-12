import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, TrendingUp, Bell, CalendarCheck2, Search, SlidersHorizontal, Plus } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { StatCard } from '@/components/dashboard/StatCard'
import { ClassCard } from '@/components/dashboard/ClassCard'
import { ScheduleClassModal } from '@/components/dashboard/ScheduleClassModal'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Tabs } from '@/components/ui/Tabs'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EngagementTrendChart } from '@/components/charts/EngagementTrendChart'
import { BehaviorPieChart } from '@/components/charts/BehaviorPieChart'
import { classesApi, reportsApi, monitoringApi } from '@/services/api/endpoints'
import { relativeTime } from '@/lib/utils'
import { Input } from '@/components/ui/Input'

type Filter = 'all' | 'live' | 'scheduled' | 'completed'

export function TeacherDashboardPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const [search, setSearch] = useState('')
  const [scheduleOpen, setScheduleOpen] = useState(false)

  const classesQuery = useQuery({ queryKey: ['classes'], queryFn: classesApi.list })
  const trendQuery = useQuery({ queryKey: ['engagement-trend'], queryFn: reportsApi.engagementTrend })
  const breakdownQuery = useQuery({ queryKey: ['behavior-breakdown'], queryFn: reportsApi.behaviorBreakdown })
  const alertsQuery = useQuery({ queryKey: ['alerts'], queryFn: monitoringApi.alerts })

  const classes = (classesQuery.data ?? []).filter((c) => {
    const matchesFilter = filter === 'all' || c.status === filter
    const matchesSearch = c.title.toLowerCase().includes(search.toLowerCase())
    return matchesFilter && matchesSearch
  })
  const liveCount = (classesQuery.data ?? []).filter((c) => c.status === 'live').length
  const todayCount = (classesQuery.data ?? []).length

  return (
    <AppShell role="teacher" title="Teacher Dashboard">
      <div className="space-y-6">
        {/* Stat row */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Today's classes" value={String(todayCount)} icon={CalendarCheck2} tone="focus" trend={{ value: 8, positive: true }} />
          <StatCard label="Live right now" value={String(liveCount)} icon={Users} tone="critical" />
          <StatCard label="Avg. engagement" value="72%" icon={TrendingUp} tone="engaged" trend={{ value: 4, positive: true }} />
          <StatCard label="Open alerts" value={String((alertsQuery.data ?? []).filter((a) => !a.acknowledged).length)} icon={Bell} tone="attention" />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Classes list */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-center pb-3">
                <div>
                  <CardTitle>Your classes</CardTitle>
                  <CardDescription>Upcoming, live, and recent sessions</CardDescription>
                </div>
                <div className="flex flex-1 items-center gap-2 sm:justify-end">
                  <div className="relative flex-1 sm:max-w-[180px]">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark" />
                    <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search" className="h-8 pl-8 text-xs" />
                  </div>
                  <button className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-light text-textmuted-light dark:border-border-dark dark:text-textmuted-dark">
                    <SlidersHorizontal className="h-3.5 w-3.5" />
                  </button>
                  <Button size="sm" onClick={() => setScheduleOpen(true)}><Plus className="h-4 w-4" />New class</Button>
                </div>
              </CardHeader>
              <CardContent className="pt-3">
                <Tabs
                  className="mb-4"
                  active={filter}
                  onChange={setFilter}
                  tabs={[
                    { value: 'all', label: 'All', count: classesQuery.data?.length },
                    { value: 'live', label: 'Live', count: (classesQuery.data ?? []).filter((c) => c.status === 'live').length },
                    { value: 'scheduled', label: 'Scheduled' },
                    { value: 'completed', label: 'Completed' },
                  ]}
                />
                {classesQuery.isLoading ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-40" />)}
                  </div>
                ) : classesQuery.isError ? (
                  <ErrorState onRetry={() => classesQuery.refetch()} />
                ) : classes.length === 0 ? (
                  <EmptyState icon={CalendarCheck2} title="No classes match" description="Try a different filter or search term." />
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {classes.map((c) => <ClassCard key={c.id} session={c} role="teacher" />)}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Alerts / recent activity */}
          <Card className="h-fit">
            <CardHeader className="pb-3">
              <CardTitle>Alert center</CardTitle>
              <CardDescription>Latest AI-flagged behavior</CardDescription>
            </CardHeader>
            <CardContent className="pt-3">
              {alertsQuery.isLoading ? (
                <div className="space-y-3">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
              ) : (
                <ul className="space-y-1 max-h-[420px] overflow-y-auto">
                  {(alertsQuery.data ?? []).slice(0, 8).map((alert) => (
                    <li key={alert.id} className="flex items-start gap-3 rounded-lg px-2 py-2.5 hover:bg-black/5 dark:hover:bg-white/5">
                      <Badge variant={alert.severity === 'critical' ? 'critical' : alert.severity === 'warning' ? 'attention' : 'neutral'} className="mt-0.5 shrink-0">
                        {alert.severity}
                      </Badge>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-text-light dark:text-text-dark">{alert.studentName}</p>
                        <p className="truncate text-xs text-textmuted-light dark:text-textmuted-dark">{alert.message}</p>
                        <p className="mt-0.5 text-[11px] text-textmuted-light dark:text-textmuted-dark">{relativeTime(alert.timestamp)}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle>Engagement trend</CardTitle>
              <CardDescription>Average engagement across all classes, last 14 days</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              {trendQuery.isLoading ? <Skeleton className="h-[260px]" /> : <EngagementTrendChart data={trendQuery.data ?? []} />}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Behavior breakdown</CardTitle>
              <CardDescription>Aggregated cognitive states this week</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              {breakdownQuery.isLoading ? <Skeleton className="h-[240px]" /> : <BehaviorPieChart data={breakdownQuery.data ?? []} />}
            </CardContent>
          </Card>
        </div>
      </div>
      <ScheduleClassModal open={scheduleOpen} onClose={() => setScheduleOpen(false)} />
    </AppShell>
  )
}
