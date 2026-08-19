import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, SlidersHorizontal, Plus, CalendarCheck2 } from 'lucide-react'

import { ClassCard } from '@/components/dashboard/ClassCard'
import { ScheduleClassModal } from '@/components/dashboard/ScheduleClassModal'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Tabs } from '@/components/ui/Tabs'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { classesApi } from '@/services/api/endpoints'

type Filter = 'all' | 'live' | 'scheduled' | 'completed'

// "Your classes" -- the teacher's own class list with search/filter/New
// class. Shared by the Teacher Dashboard and the dedicated Teacher
// Classes page (/teacher/classes) so both render from exactly one
// classesApi.list fetch/UI implementation, never two diverging copies.
// (React Query dedupes both subscriptions to the same ['classes']
// cache entry, so using this in two places never means a duplicate
// network call.)
export function TeacherClassesCard() {
  const [filter, setFilter] = useState<Filter>('all')
  const [search, setSearch] = useState('')
  const [scheduleOpen, setScheduleOpen] = useState(false)

  const classesQuery = useQuery({ queryKey: ['classes'], queryFn: classesApi.list })

  const classes = (classesQuery.data ?? []).filter((c) => {
    const matchesFilter = filter === 'all' || c.status === filter
    const matchesSearch = c.title.toLowerCase().includes(search.toLowerCase())
    return matchesFilter && matchesSearch
  })

  return (
    <>
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
      <ScheduleClassModal open={scheduleOpen} onClose={() => setScheduleOpen(false)} />
    </>
  )
}
