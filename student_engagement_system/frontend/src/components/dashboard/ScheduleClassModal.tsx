import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Zap, CalendarClock } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Input, Label } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { classesApi } from '@/services/api/endpoints'

const SUBJECTS = ['Machine Learning', 'Data Structures', 'Computer Vision', 'Operating Systems', 'DBMS']

export function ScheduleClassModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [mode, setMode] = useState<'now' | 'later'>('now')
  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState(SUBJECTS[0])
  const [date, setDate] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const createMutation = useMutation({
  mutationFn: classesApi.create,

  onSuccess: (newClass) => {
    console.log('CLASS CREATED:', newClass)

    queryClient.invalidateQueries({ queryKey: ['classes'] })
    onClose()
    setTitle('')

    if (mode === 'now') {
      navigate(`/teacher/lobby/${newClass.id}`)
    }
  },

  onError: (error) => {
    console.error('CLASS CREATION FAILED:', error)

    alert(
      error instanceof Error
        ? error.message
        : 'Unable to create class'
    )
  },
})

  const handleSubmit = () => {
    createMutation.mutate({
      title,
      subject,
      scheduledStart: date || new Date().toISOString(),
      startNow: mode === 'now',
    })
  }

  return (
    <Modal open={open} onClose={onClose} title="New class session">
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => setMode('now')}
            className={cn(
              'flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-colors',
              mode === 'now' ? 'border-focus-500 bg-focus-500/10' : 'border-border-light dark:border-border-dark',
            )}
          >
            <Zap className="h-5 w-5 text-focus-500" />
            <div>
              <p className="text-sm font-semibold text-text-light dark:text-text-dark">Start instantly</p>
              <p className="text-xs text-textmuted-light dark:text-textmuted-dark">Go live right now</p>
            </div>
          </button>
          <button
            onClick={() => setMode('later')}
            className={cn(
              'flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-colors',
              mode === 'later' ? 'border-focus-500 bg-focus-500/10' : 'border-border-light dark:border-border-dark',
            )}
          >
            <CalendarClock className="h-5 w-5 text-focus-500" />
            <div>
              <p className="text-sm font-semibold text-text-light dark:text-text-dark">Schedule for later</p>
              <p className="text-xs text-textmuted-light dark:text-textmuted-dark">Pick a date & time</p>
            </div>
          </button>
        </div>

        <div>
          <Label>Class title</Label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Neural Networks — Live Session" />
        </div>

        <div>
          <Label>Subject</Label>
          <select
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="h-10 w-full rounded-lg border border-border-light bg-surface-light px-3 text-sm text-text-light outline-none focus:border-focus-500 dark:border-border-dark dark:bg-surface-dark dark:text-text-dark"
          >
            {SUBJECTS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {mode === 'later' && (
          <div>
            <Label>Date & time</Label>
            <Input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit} loading={createMutation.isPending} disabled={!title.trim()}>
            {mode === 'now' ? 'Start now' : 'Schedule class'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
