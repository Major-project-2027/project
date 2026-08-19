import { useQuery } from '@tanstack/react-query'
import { Users, TrendingUp, CalendarCheck2 } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { StatCard } from '@/components/dashboard/StatCard'
import { TeacherClassesCard } from '@/components/dashboard/TeacherClassesCard'
import { classesApi } from '@/services/api/endpoints'

export function TeacherDashboardPage() {
  const classesQuery = useQuery({ queryKey: ['classes'], queryFn: classesApi.list })

  const liveCount = (classesQuery.data ?? []).filter((c) => c.status === 'live').length
  const todayCount = (classesQuery.data ?? []).length

  return (
    <AppShell role="teacher" title="Teacher Dashboard">
      <div className="space-y-6">
        {/* Stat row */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard label="Today's classes" value={String(todayCount)} icon={CalendarCheck2} tone="focus" trend={{ value: 8, positive: true }} />
          <StatCard label="Live right now" value={String(liveCount)} icon={Users} tone="critical" />
          <StatCard label="Avg. engagement" value="72%" icon={TrendingUp} tone="engaged" trend={{ value: 4, positive: true }} />
        </div>

        <TeacherClassesCard />
      </div>
    </AppShell>
  )
}
