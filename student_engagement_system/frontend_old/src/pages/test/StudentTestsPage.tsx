import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ListChecks, ScanFace, Clock } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { testsApi } from '@/services/api/endpoints'
import { formatDateTime } from '@/lib/utils'

export function StudentTestsPage() {
  const testsQuery = useQuery({ queryKey: ['tests'], queryFn: testsApi.list })
  const navigate = useNavigate()

  return (
    <AppShell role="student" title="Tests">
      <Card>
        <CardHeader className="pb-3"><CardTitle>Your tests</CardTitle><CardDescription>Scheduled assessments and past results</CardDescription></CardHeader>
        <CardContent className="pt-3">
          {testsQuery.isLoading ? (
            <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
          ) : (testsQuery.data ?? []).length === 0 ? (
            <EmptyState icon={ListChecks} title="No tests scheduled" description="Your teacher hasn't assigned any tests yet." />
          ) : (
            <div className="space-y-3">
              {(testsQuery.data ?? []).map((t) => (
                <div key={t.id} className="flex flex-col gap-3 rounded-xl border border-border-light p-4 sm:flex-row sm:items-center sm:justify-between dark:border-border-dark">
                  <div>
                    <p className="text-sm font-semibold text-text-light dark:text-text-dark">{t.title}</p>
                    <p className="flex items-center gap-1 text-xs text-textmuted-light dark:text-textmuted-dark"><Clock className="h-3.5 w-3.5" />{t.durationMinutes} min · {t.totalMarks} marks · {formatDateTime(t.scheduledStart)}</p>
                    {t.proctoringEnabled && <p className="mt-1 flex items-center gap-1 text-xs text-focus-500"><ScanFace className="h-3.5 w-3.5" />Face authentication required to join</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={t.status === 'scheduled' ? 'attention' : t.status === 'completed' ? 'engaged' : 'neutral'}>{t.status}</Badge>
                    {t.status === 'scheduled' && <Button size="sm" onClick={() => navigate(`/student/tests/${t.id}/take`)}>Join test</Button>}
                    {t.status === 'completed' && <Button size="sm" variant="outline" onClick={() => navigate(`/student/tests/${t.id}/result`)}>View result</Button>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </AppShell>
  )
}
