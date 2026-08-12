import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ShieldCheck, Clock, ChevronLeft, ChevronRight, Flag } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { generateTests } from '@/mocks/data'
import { cn } from '@/lib/utils'

export function StudentTestTakingPage() {
  const { testId } = useParams()
  const navigate = useNavigate()
  const test = generateTests().find((t) => t.id === testId) ?? generateTests()[0]

  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string | number>>({})
  const [flagged, setFlagged] = useState<Set<string>>(new Set())
  const [remaining, setRemaining] = useState(test.durationMinutes * 60)
  const [submitOpen, setSubmitOpen] = useState(false)

  const submit = useCallback((_auto = false) => {
    navigate(`/student/tests/${test.id}/result`)
  }, [navigate, test.id])

  useEffect(() => {
    if (remaining <= 0) { submit(true); return }
    const t = setInterval(() => setRemaining((r) => r - 1), 1000)
    return () => clearInterval(t)
  }, [remaining, submit])

  const question = test.questions[current] ?? test.questions[0]
  const mins = Math.floor(remaining / 60)
  const secs = remaining % 60
  const lowTime = remaining < 60

  const toggleFlag = (id: string) => setFlagged((f) => {
    const next = new Set(f)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })

  return (
    <div className="min-h-screen bg-bg-light dark:bg-bg-dark">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border-light bg-surface-light px-4 py-3 dark:border-border-dark dark:bg-surface-dark md:px-8">
        <div>
          <p className="font-display text-sm font-semibold text-text-light dark:text-text-dark">{test.title}</p>
          <p className="flex items-center gap-1 text-xs text-engaged-600 dark:text-engaged-400"><ShieldCheck className="h-3.5 w-3.5" />Proctoring active — face auth verified</p>
        </div>
        <div className={cn('flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-mono text-sm font-semibold', lowTime ? 'bg-critical-500/10 text-critical-600 dark:text-critical-400' : 'bg-focus-500/10 text-focus-600 dark:text-focus-400')}>
          <Clock className="h-4 w-4" />{String(mins).padStart(2, '0')}:{String(secs).padStart(2, '0')}
        </div>
      </header>

      <div className="mx-auto grid max-w-5xl gap-6 px-4 py-6 md:grid-cols-[1fr_220px] md:px-8">
        <div>
          <div className="rounded-2xl border border-border-light bg-surface-light p-6 dark:border-border-dark dark:bg-surface-dark">
            <div className="mb-4 flex items-center justify-between">
              <Badge variant="focus">Question {current + 1} of {test.questions.length} · {question?.marks} mark{question?.marks !== 1 ? 's' : ''}</Badge>
              <button onClick={() => toggleFlag(question.id)} className={cn('flex items-center gap-1 text-xs font-medium', flagged.has(question.id) ? 'text-attention-500' : 'text-textmuted-light dark:text-textmuted-dark')}>
                <Flag className="h-3.5 w-3.5" />{flagged.has(question.id) ? 'Flagged' : 'Flag for review'}
              </button>
            </div>
            <p className="text-base font-medium text-text-light dark:text-text-dark">{question?.prompt}</p>

            <div className="mt-5 space-y-2.5">
              {(question?.type === 'mcq' || question?.type === 'true_false') && question.options?.map((opt, i) => (
                <label key={i} className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-xl border p-3 text-sm transition-colors',
                  answers[question.id] === i ? 'border-focus-500 bg-focus-500/5' : 'border-border-light dark:border-border-dark',
                )}>
                  <input type="radio" className="accent-[#4F5DFF]" checked={answers[question.id] === i} onChange={() => setAnswers((a) => ({ ...a, [question.id]: i }))} />
                  <span className="text-text-light dark:text-text-dark">{opt}</span>
                </label>
              ))}
              {(question?.type === 'short_answer' || question?.type === 'essay') && (
                <textarea
                  value={(answers[question.id] as string) ?? ''}
                  onChange={(e) => setAnswers((a) => ({ ...a, [question.id]: e.target.value }))}
                  rows={question.type === 'essay' ? 8 : 3}
                  placeholder="Type your answer..."
                  className="w-full rounded-xl border border-border-light bg-transparent p-3 text-sm outline-none focus:border-focus-500 dark:border-border-dark"
                />
              )}
            </div>

            <div className="mt-6 flex items-center justify-between">
              <Button variant="outline" disabled={current === 0} onClick={() => setCurrent((c) => c - 1)}><ChevronLeft className="h-4 w-4" />Previous</Button>
              {current < test.questions.length - 1 ? (
                <Button onClick={() => setCurrent((c) => c + 1)}>Next<ChevronRight className="h-4 w-4" /></Button>
              ) : (
                <Button variant="danger" onClick={() => setSubmitOpen(true)}>Submit test</Button>
              )}
            </div>
          </div>
        </div>

        {/* Question navigator */}
        <div className="h-fit rounded-2xl border border-border-light bg-surface-light p-4 dark:border-border-dark dark:bg-surface-dark">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-textmuted-light dark:text-textmuted-dark">Questions</p>
          <div className="grid grid-cols-5 gap-2 md:grid-cols-4">
            {test.questions.map((q, i) => (
              <button
                key={q.id}
                onClick={() => setCurrent(i)}
                className={cn(
                  'flex h-9 w-9 items-center justify-center rounded-lg text-xs font-medium',
                  i === current ? 'bg-focus-500 text-white' : answers[q.id] !== undefined ? 'bg-engaged-500/15 text-engaged-600 dark:text-engaged-400' : 'bg-black/5 text-textmuted-light dark:bg-white/10 dark:text-textmuted-dark',
                  flagged.has(q.id) && 'ring-2 ring-attention-500',
                )}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <Button className="mt-4 w-full" variant="secondary" onClick={() => setSubmitOpen(true)}>Submit test</Button>
        </div>
      </div>

      <Modal open={submitOpen} onClose={() => setSubmitOpen(false)} title="Submit test?">
        <p className="text-sm text-textmuted-light dark:text-textmuted-dark">
          You've answered {Object.keys(answers).length} of {test.questions.length} questions. Once submitted, you cannot make further changes.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setSubmitOpen(false)}>Keep working</Button>
          <Button variant="danger" onClick={() => submit(false)}>Submit now</Button>
        </div>
      </Modal>
    </div>
  )
}
