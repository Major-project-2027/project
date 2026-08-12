import { useQuery } from '@tanstack/react-query'
import { CalendarCheck2, ClipboardList, ListChecks, Camera, Mic, Bell } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { StatCard } from '@/components/dashboard/StatCard'
import { ClassCard } from '@/components/dashboard/ClassCard'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { Switch } from '@/components/ui/Switch'
import { Badge } from '@/components/ui/Badge'
import { classesApi, notificationsApi, testsApi } from '@/services/api/endpoints'
import { currentStudent } from '@/mocks/data'
import { relativeTime, formatDateTime } from '@/lib/utils'
import { useState } from 'react'

export function StudentDashboardPage() {
  const classesQuery = useQuery({ queryKey: ['classes'], queryFn: classesApi.list })
  const notificationsQuery = useQuery({ queryKey: ['notifications'], queryFn: notificationsApi.list })
  const testsQuery = useQuery({ queryKey: ['tests'], queryFn: testsApi.list })
  const [cameraOn, setCameraOn] = useState(currentStudent.cameraEnabled)
  const [micOn, setMicOn] = useState(currentStudent.micEnabled)

  const upcoming = (classesQuery.data ?? []).filter((c) => c.status !== 'completed')
  const today = upcoming.slice(0, 4)

  return (
    <AppShell role="student" title="Student Dashboard">
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Today's schedule" value={String(today.length)} icon={CalendarCheck2} tone="focus" />
          <StatCard label="Attendance rate" value="91%" icon={ClipboardList} tone="engaged" trend={{ value: 2, positive: true }} />
          <StatCard label="Pending tests" value={String((testsQuery.data ?? []).filter((t) => t.status === 'scheduled').length)} icon={ListChecks} tone="attention" />
          <StatCard label="Unread alerts" value={String((notificationsQuery.data ?? []).filter((n) => !n.read).length)} icon={Bell} tone="critical" />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Upcoming classes</CardTitle>
                <CardDescription>Join a live session or view what's scheduled</CardDescription>
              </CardHeader>
              <CardContent className="pt-3">
                {classesQuery.isLoading ? (
                  <div className="grid gap-4 sm:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-40" />)}</div>
                ) : today.length === 0 ? (
                  <EmptyState icon={CalendarCheck2} title="Nothing scheduled" description="Your upcoming classes will show up here." />
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {today.map((c) => <ClassCard key={c.id} session={c} role="student" />)}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Tests & assignments</CardTitle>
                <CardDescription>Stay on top of what's due</CardDescription>
              </CardHeader>
              <CardContent className="pt-3 space-y-2">
                {(testsQuery.data ?? []).map((t) => (
                  <div key={t.id} className="flex items-center justify-between rounded-lg border border-border-light p-3 dark:border-border-dark">
                    <div>
                      <p className="text-sm font-medium text-text-light dark:text-text-dark">{t.title}</p>
                      <p className="text-xs text-textmuted-light dark:text-textmuted-dark">{t.subject} · {t.durationMinutes} min · {formatDateTime(t.scheduledStart)}</p>
                    </div>
                    <Badge variant={t.status === 'scheduled' ? 'attention' : t.status === 'completed' ? 'engaged' : 'neutral'}>{t.status}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Device status</CardTitle>
                <CardDescription>Controls used during live sessions</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-3">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-text-light dark:text-text-dark"><Camera className="h-4 w-4" />Camera</span>
                  <Switch checked={cameraOn} onChange={setCameraOn} label="Toggle camera" />
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-text-light dark:text-text-dark"><Mic className="h-4 w-4" />Microphone</span>
                  <Switch checked={micOn} onChange={setMicOn} label="Toggle microphone" />
                </div>
                <p className="rounded-lg bg-focus-500/5 p-2.5 text-xs text-textmuted-light dark:text-textmuted-dark">
                  Face authentication is required before joining any monitored session. Your teacher controls whether camera use is mandatory for a given class.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Notifications</CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                {notificationsQuery.isLoading ? (
                  <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
                ) : (
                  <ul className="space-y-1">
                    {(notificationsQuery.data ?? []).slice(0, 5).map((n) => (
                      <li key={n.id} className="rounded-lg px-2 py-2 hover:bg-black/5 dark:hover:bg-white/5">
                        <p className="text-sm font-medium text-text-light dark:text-text-dark">{n.title}</p>
                        <p className="text-xs text-textmuted-light dark:text-textmuted-dark">{relativeTime(n.timestamp)}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
