import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Users, Clock, Radio, PlayCircle, LogIn } from 'lucide-react'
import type { ClassSession } from '@/types/domain'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { formatTime, engagementTone, cn } from '@/lib/utils'
import { classesApi } from '@/services/api/endpoints'

const STATUS_BADGE: Record<ClassSession['status'], { variant: 'neutral' | 'engaged' | 'attention' | 'critical'; label: string }> = {
  scheduled: { variant: 'neutral', label: 'Scheduled' },
  live: { variant: 'critical', label: 'Live now' },
  completed: { variant: 'engaged', label: 'Completed' },
  cancelled: { variant: 'attention', label: 'Cancelled' },
}

export function ClassCard({ session, role }: { session: ClassSession; role: 'teacher' | 'student' }) {
  const badge = STATUS_BADGE[session.status]
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const startMutation = useMutation({
    mutationFn: () => classesApi.start(session.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classes'] })
      navigate(`/teacher/lobby/${session.id}`)
    },
  })

  return (
    <Card className="overflow-hidden">
      <div className="h-1.5" style={{ backgroundColor: session.coverColor }} />
      <div className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-display text-sm font-semibold text-text-light dark:text-text-dark">{session.title}</p>
            <p className="mt-0.5 text-xs text-textmuted-light dark:text-textmuted-dark">{session.teacherName}</p>
          </div>
          <Badge variant={badge.variant}>{session.status === 'live' && <Radio className="h-3 w-3" />}{badge.label}</Badge>
        </div>

        <div className="mt-3 flex items-center gap-4 text-xs text-textmuted-light dark:text-textmuted-dark">
          <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{formatTime(session.scheduledStart)}</span>
          <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />{session.studentsPresent ?? session.studentsEnrolled} {session.status !== 'scheduled' ? `/ ${session.studentsEnrolled}` : 'enrolled'}</span>
        </div>

        {session.avgEngagement !== undefined && (
          <div className="mt-3 flex items-center gap-2">
            <div className="h-1.5 flex-1 rounded-full bg-black/8 dark:bg-white/10">
              <div
                className={cn('h-full rounded-full', {
                  engaged: 'bg-engaged-500',
                  attention: 'bg-attention-500',
                  critical: 'bg-critical-500',
                }[engagementTone(session.avgEngagement)])}
                style={{ width: `${session.avgEngagement}%` }}
              />
            </div>
            <span className="font-mono text-xs text-textmuted-light dark:text-textmuted-dark">{session.avgEngagement}%</span>
          </div>
        )}

        <div className="mt-4 flex gap-2">
          {/* TEACHER actions */}
          {role === 'teacher' && session.status === 'scheduled' && (
            <Button size="sm" className="w-full" onClick={() => startMutation.mutate()} loading={startMutation.isPending}>
              <PlayCircle className="h-4 w-4" />Start class
            </Button>
          )}
          {role === 'teacher' && session.status === 'live' && (
            <Button size="sm" className="w-full" onClick={() => navigate(`/teacher/lobby/${session.id}`)}>
              <LogIn className="h-4 w-4" />Manage session
            </Button>
          )}
          {role === 'teacher' && session.status === 'completed' && (
            <Button size="sm" variant="secondary" className="w-full" onClick={() => navigate(`/teacher/classroom/${session.id}/report`)}>
              View report
            </Button>
          )}

          {/* STUDENT actions */}
          {role === 'student' && session.status === 'live' && (
            <Button size="sm" className="w-full" onClick={() => navigate(`/student/lobby/${session.id}`)}>
              <LogIn className="h-4 w-4" />Join
            </Button>
          )}
          {role === 'student' && session.status === 'scheduled' && (
            <Button size="sm" variant="outline" className="w-full" disabled>
              Not started yet
            </Button>
          )}
          {role === 'student' && session.status === 'completed' && (
            <Button size="sm" variant="secondary" className="w-full" onClick={() => navigate(`/student/classroom/${session.id}/report`)}>
              View my report
            </Button>
          )}
        </div>
      </div>
    </Card>
  )
}
