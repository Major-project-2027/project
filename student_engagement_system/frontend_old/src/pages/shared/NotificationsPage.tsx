import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bell, ShieldAlert, Info, ClipboardList, CalendarClock, CheckCheck } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Tabs } from '@/components/ui/Tabs'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { notificationsApi } from '@/services/api/endpoints'
import { relativeTime, cn } from '@/lib/utils'
import type { AppNotification, UserRole } from '@/types/domain'

const CATEGORY_ICON: Record<AppNotification['category'], typeof Bell> = {
  ai_alert: ShieldAlert,
  system: Info,
  class: CalendarClock,
  attendance: ClipboardList,
}

type Filter = 'all' | AppNotification['category']

export function NotificationsPage({ role }: { role: UserRole }) {
  const [filter, setFilter] = useState<Filter>('all')
  const query = useQuery({ queryKey: ['notifications'], queryFn: notificationsApi.list })
  const notifications = (query.data ?? []).filter((n) => filter === 'all' || n.category === filter)

  return (
    <AppShell role={role} title="Notifications">
      <Card>
        <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <div>
            <CardTitle>All notifications</CardTitle>
            <CardDescription>Real-time AI alerts and system updates</CardDescription>
          </div>
          <Button variant="ghost" size="sm" className="sm:ml-auto"><CheckCheck className="h-4 w-4" />Mark all as read</Button>
        </CardHeader>
        <CardContent className="pt-3">
          <Tabs
            className="mb-4 flex-wrap"
            active={filter}
            onChange={setFilter}
            tabs={[
              { value: 'all', label: 'All' },
              { value: 'ai_alert', label: 'AI alerts' },
              { value: 'attendance', label: 'Attendance' },
              { value: 'class', label: 'Class' },
              { value: 'system', label: 'System' },
            ]}
          />
          {query.isLoading ? (
            <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
          ) : notifications.length === 0 ? (
            <EmptyState icon={Bell} title="You're all caught up" description="New alerts and updates will appear here." />
          ) : (
            <ul className="divide-y divide-border-light dark:divide-border-dark">
              {notifications.map((n) => {
                const Icon = CATEGORY_ICON[n.category]
                return (
                  <li key={n.id} className={cn('flex items-start gap-3 py-3', !n.read && 'bg-focus-500/[0.03]')}>
                    <div className={cn(
                      'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl',
                      n.severity === 'critical' ? 'bg-critical-500/10 text-critical-500' : n.severity === 'warning' ? 'bg-attention-500/10 text-attention-500' : 'bg-focus-500/10 text-focus-500',
                    )}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-text-light dark:text-text-dark">{n.title}</p>
                      <p className="text-sm text-textmuted-light dark:text-textmuted-dark">{n.message}</p>
                      <p className="mt-0.5 text-xs text-textmuted-light dark:text-textmuted-dark">{relativeTime(n.timestamp)}</p>
                    </div>
                    {!n.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-focus-500" />}
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </AppShell>
  )
}
