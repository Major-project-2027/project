import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2 } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { StudentPicker } from '@/components/access/StudentPicker'
import { accessApi } from '@/services/api/endpoints'

/**
 * The teacher's student roster: which registered students this teacher
 * works with. When creating a class (or editing its access), the teacher
 * picks that class's allowed students from this roster. Existing student
 * accounts are used as-is -- nothing is duplicated.
 */
export function ManageStudentsPage() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [savedAt, setSavedAt] = useState<number | null>(null)

  const studentsQuery = useQuery({
    queryKey: ['teacher-students'],
    queryFn: accessApi.listStudents,
  })

  useEffect(() => {
    if (studentsQuery.data) {
      setSelected(new Set(studentsQuery.data.filter((s) => s.inRoster).map((s) => s.studentId)))
    }
  }, [studentsQuery.data])

  const saveMutation = useMutation({
    mutationFn: () => accessApi.saveRoster(Array.from(selected)),
    onSuccess: () => {
      setSavedAt(Date.now())
      queryClient.invalidateQueries({ queryKey: ['teacher-students'] })
      queryClient.invalidateQueries({ queryKey: ['class-students'] })
    },
  })

  const dirty =
    studentsQuery.data !== undefined &&
    (studentsQuery.data.filter((s) => s.inRoster).length !== selected.size ||
      studentsQuery.data.some((s) => s.inRoster !== selected.has(s.studentId)))

  return (
    <AppShell role="teacher" title="Students">
      <div className="space-y-6">
        <Card>
          <CardHeader className="flex-col items-stretch gap-3 pb-3 sm:flex-row sm:items-center">
            <div>
              <CardTitle>Manage students</CardTitle>
              <CardDescription>
                Select the registered students in your roster. For each class you then choose which of
                them may join — students who aren't allowed can't see or join that class.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2 sm:ml-auto">
              {savedAt && !dirty && (
                <span className="flex items-center gap-1 text-xs text-engaged-500">
                  <CheckCircle2 className="h-4 w-4" />
                  Saved
                </span>
              )}
              <Button onClick={() => saveMutation.mutate()} loading={saveMutation.isPending} disabled={!dirty}>
                Save selection
              </Button>
            </div>
          </CardHeader>

          <CardContent className="pt-3">
            {studentsQuery.error && (
              <p className="mb-3 rounded-lg bg-critical-500/10 px-3 py-2 text-sm text-critical-500">
                {(studentsQuery.error as Error).message}
              </p>
            )}
            {saveMutation.error && (
              <p className="mb-3 rounded-lg bg-critical-500/10 px-3 py-2 text-sm text-critical-500">
                {(saveMutation.error as Error).message}
              </p>
            )}

            <StudentPicker
              students={studentsQuery.data ?? []}
              selected={selected}
              onChange={(next) => {
                setSelected(next)
                setSavedAt(null)
              }}
              loading={studentsQuery.isLoading}
              emptyMessage="No students have registered yet."
            />
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
