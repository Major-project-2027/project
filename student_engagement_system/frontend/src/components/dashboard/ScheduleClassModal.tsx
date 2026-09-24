import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Zap, CalendarClock, ArrowLeft } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Input, Label } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { accessApi, classesApi } from '@/services/api/endpoints'
import { StudentPicker } from '@/components/access/StudentPicker'

const SUBJECTS = ['Machine Learning', 'Data Structures', 'Computer Vision', 'Operating Systems', 'DBMS']

export function ScheduleClassModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [mode, setMode] = useState<'now' | 'later'>('now')
  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState(SUBJECTS[0])
  const [date, setDate] = useState('')
  // Step 2: which students may join this class (from the teacher's roster).
  const [step, setStep] = useState<1 | 2>(1)
  const [selectedStudents, setSelectedStudents] = useState<Set<number>>(new Set())
  const [showAllStudents, setShowAllStudents] = useState(false)
  const navigate = useNavigate()

  const studentsQuery = useQuery({
    queryKey: ['teacher-students'],
    queryFn: accessApi.listStudents,
    enabled: open && step === 2,
  })
  const roster = (studentsQuery.data ?? []).filter((s) => s.inRoster)
  const pickable = showAllStudents ? studentsQuery.data ?? [] : roster

  const close = () => {
    setStep(1)
    setSelectedStudents(new Set())
    setShowAllStudents(false)
    onClose()
  }
  const queryClient = useQueryClient()

  const createMutation = useMutation({
  mutationFn: classesApi.create,

  onSuccess: (newClass) => {
    console.log('CLASS CREATED:', newClass)

    queryClient.invalidateQueries({ queryKey: ['classes'] })
    close()
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
      studentIds: Array.from(selectedStudents),
    })
  }

  return (
    <Modal open={open} onClose={close} title={step === 1 ? 'New class session' : 'Select students'} className={step === 2 ? 'max-w-xl' : undefined}>
      {step === 2 ? (
        <div className="space-y-4">
          <p className="text-sm text-textmuted-light dark:text-textmuted-dark">
            Only the students you select can see and join <span className="font-medium text-text-light dark:text-text-dark">{title}</span>.
            You can change this later from the class card.
          </p>

          {studentsQuery.error && (
            <p className="rounded-lg bg-critical-500/10 px-3 py-2 text-sm text-critical-500">
              {(studentsQuery.error as Error).message}
            </p>
          )}

          <StudentPicker
            students={pickable}
            selected={selectedStudents}
            onChange={setSelectedStudents}
            loading={studentsQuery.isLoading}
            emptyMessage="Your roster is empty. Add students under Students, or show all registered students."
          />

          <label className="flex items-center gap-2 text-xs text-textmuted-light dark:text-textmuted-dark">
            <input
              type="checkbox"
              checked={showAllStudents}
              onChange={(e) => setShowAllStudents(e.target.checked)}
              className="h-4 w-4 accent-focus-500"
            />
            Show all registered students (not only my roster) ·{' '}
            <Link to="/teacher/students" className="text-focus-500 hover:underline" onClick={close}>
              Manage roster
            </Link>
          </label>

          {selectedStudents.size === 0 && (
            <p className="rounded-lg bg-attention-500/10 px-3 py-2 text-xs text-attention-600 dark:text-attention-300">
              No students selected — nobody will be able to join until you allow students.
            </p>
          )}

          <div className="flex justify-between gap-2">
            <Button variant="ghost" onClick={() => setStep(1)}>
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={close}>Cancel</Button>
              <Button onClick={handleSubmit} loading={createMutation.isPending}>
                {mode === 'now' ? `Start now (${selectedStudents.size})` : `Schedule class (${selectedStudents.size})`}
              </Button>
            </div>
          </div>
        </div>
      ) : (
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
          <Button variant="outline" onClick={close}>Cancel</Button>
          <Button onClick={() => setStep(2)} disabled={!title.trim()}>
            Next: select students
          </Button>
        </div>
      </div>
      )}
    </Modal>
  )
}
