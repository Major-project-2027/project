import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2, ListChecks, PlayCircle, Eye } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input, Label } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { Badge } from '@/components/ui/Badge'
import { Switch } from '@/components/ui/Switch'
import { Skeleton } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { testsApi } from '@/services/api/endpoints'
import { formatDateTime } from '@/lib/utils'
import type { QuestionType, TestQuestion } from '@/types/domain'

const QUESTION_TYPES: { value: QuestionType; label: string }[] = [
  { value: 'mcq', label: 'Multiple choice' },
  { value: 'true_false', label: 'True / False' },
  { value: 'short_answer', label: 'Short answer' },
  { value: 'essay', label: 'Essay' },
]

export function TeacherTestsPage() {
  const testsQuery = useQuery({ queryKey: ['tests'], queryFn: testsApi.list })
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [questions, setQuestions] = useState<TestQuestion[]>([
    { id: 'q1', type: 'mcq', prompt: '', options: ['', '', '', ''], marks: 1 },
  ])
  const [proctoring, setProctoring] = useState(true)

  const addQuestion = (type: QuestionType) => {
    setQuestions((qs) => [...qs, { id: `q${qs.length + 1}-${Date.now()}`, type, prompt: '', options: type === 'mcq' ? ['', '', '', ''] : type === 'true_false' ? ['True', 'False'] : undefined, marks: 1 }])
  }
  const removeQuestion = (id: string) => setQuestions((qs) => qs.filter((q) => q.id !== id))

  return (
    <AppShell role="teacher" title="Tests">
      <Card>
        <CardHeader className="flex-col items-stretch gap-3 sm:flex-row sm:items-center">
          <div>
            <CardTitle>Online tests</CardTitle>
            <CardDescription>Create, schedule, and monitor assessments</CardDescription>
          </div>
          <Button size="sm" className="sm:ml-auto" onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4" />Create test</Button>
        </CardHeader>
        <CardContent className="pt-3">
          {testsQuery.isLoading ? (
            <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
          ) : (testsQuery.data ?? []).length === 0 ? (
            <EmptyState icon={ListChecks} title="No tests yet" description="Create your first test to get started." action={<Button size="sm" onClick={() => setCreateOpen(true)}>Create test</Button>} />
          ) : (
            <div className="space-y-2">
              {(testsQuery.data ?? []).map((t) => (
                <div key={t.id} className="flex flex-col gap-3 rounded-xl border border-border-light p-4 sm:flex-row sm:items-center sm:justify-between dark:border-border-dark">
                  <div>
                    <p className="text-sm font-semibold text-text-light dark:text-text-dark">{t.title}</p>
                    <p className="text-xs text-textmuted-light dark:text-textmuted-dark">{t.subject} · {t.durationMinutes} min · {t.totalMarks} marks · {formatDateTime(t.scheduledStart)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={t.status === 'scheduled' ? 'attention' : t.status === 'live' ? 'critical' : t.status === 'completed' ? 'engaged' : 'neutral'}>{t.status}</Badge>
                    {t.status === 'scheduled' && (
                      <Button size="sm" onClick={() => navigate(`/teacher/tests/${t.id}/monitor`)}><PlayCircle className="h-4 w-4" />Start</Button>
                    )}
                    {t.status === 'completed' && (
                      <Button size="sm" variant="outline" onClick={() => navigate(`/teacher/tests/${t.id}/results`)}><Eye className="h-4 w-4" />Results</Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create a new test" className="max-w-2xl">
        <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
          <div className="grid gap-4 sm:grid-cols-2">
            <div><Label>Test title</Label><Input placeholder="Neural Networks — Quiz" /></div>
            <div><Label>Subject</Label><Input placeholder="Machine Learning" /></div>
            <div><Label>Duration (minutes)</Label><Input type="number" defaultValue={30} /></div>
            <div><Label>Scheduled start</Label><Input type="datetime-local" /></div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border-light p-3 dark:border-border-dark">
            <div>
              <p className="text-sm font-medium text-text-light dark:text-text-dark">AI proctoring</p>
              <p className="text-xs text-textmuted-light dark:text-textmuted-dark">Monitor face auth, gaze, and object detection during the test</p>
            </div>
            <Switch checked={proctoring} onChange={setProctoring} />
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <Label className="mb-0">Question bank</Label>
              <div className="flex flex-wrap gap-1.5">
                {QUESTION_TYPES.map((qt) => (
                  <Button key={qt.value} size="sm" variant="outline" onClick={() => addQuestion(qt.value)}><Plus className="h-3.5 w-3.5" />{qt.label}</Button>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              {questions.map((q, idx) => (
                <div key={q.id} className="rounded-lg border border-border-light p-3 dark:border-border-dark">
                  <div className="mb-2 flex items-center justify-between">
                    <Badge variant="focus">Q{idx + 1} · {QUESTION_TYPES.find((t) => t.value === q.type)?.label}</Badge>
                    <button onClick={() => removeQuestion(q.id)} className="text-textmuted-light hover:text-critical-500"><Trash2 className="h-4 w-4" /></button>
                  </div>
                  <Input placeholder="Question prompt" defaultValue={q.prompt} />
                  {q.options && (
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      {q.options.map((opt, i) => (
                        <Input key={i} placeholder={`Option ${i + 1}`} defaultValue={opt} />
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={() => setCreateOpen(false)}>Save test</Button>
          </div>
        </div>
      </Modal>
    </AppShell>
  )
}
