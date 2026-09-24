import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { StudentPicker } from '@/components/access/StudentPicker'
import { accessApi } from '@/services/api/endpoints'

/**
 * Edit which students may join one class. Lists the teacher's roster plus
 * anyone already allowed. While the class is live, already-allowed
 * students can't be removed (nobody is cut off mid-class) -- the server
 * enforces the same rule.
 */
export function AllowedStudentsModal({
  classId,
  className,
  open,
  onClose,
}: {
  classId: string
  className: string
  open: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const query = useQuery({
    queryKey: ['class-students', classId],
    queryFn: () => accessApi.classStudents(classId),
    enabled: open,
  })

  useEffect(() => {
    if (query.data) {
      setSelected(new Set(query.data.allowedStudentIds))
    }
  }, [query.data])

  const saveMutation = useMutation({
    mutationFn: () => accessApi.setClassStudents(classId, Array.from(selected)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['class-students', classId] })
      queryClient.invalidateQueries({ queryKey: ['classes'] })
      onClose()
    },
  })

  const locked = query.data?.isLive ? new Set(query.data.allowedStudentIds) : undefined

  return (
    <Modal open={open} onClose={onClose} title={`Allowed students — ${className}`} className="max-w-xl">
      <div className="space-y-4">
        <p className="text-sm text-textmuted-light dark:text-textmuted-dark">
          Only the students selected here can see and join this class. Choose from your{' '}
          <Link to="/teacher/students" className="text-focus-500 hover:underline" onClick={onClose}>
            student roster
          </Link>
          .
        </p>

        {query.error && (
          <p className="rounded-lg bg-critical-500/10 px-3 py-2 text-sm text-critical-500">
            {(query.error as Error).message}
          </p>
        )}

        <StudentPicker
          students={query.data?.students ?? []}
          selected={selected}
          onChange={setSelected}
          loading={query.isLoading}
          lockedIds={locked}
          lockedReason="students already allowed can't be removed while the class is live"
          emptyMessage="Your roster is empty. Add students under Students first."
        />

        {saveMutation.error && (
          <p className="rounded-lg bg-critical-500/10 px-3 py-2 text-sm text-critical-500">
            {(saveMutation.error as Error).message}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => saveMutation.mutate()} loading={saveMutation.isPending} disabled={query.isLoading}>
            Save
          </Button>
        </div>
      </div>
    </Modal>
  )
}
