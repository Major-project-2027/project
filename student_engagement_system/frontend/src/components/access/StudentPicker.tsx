import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Skeleton } from '@/components/ui/Skeleton'
import type { StudentSummary } from '@/services/api/endpoints'
import { cn } from '@/lib/utils'

/**
 * Checkbox list of students with search, Select all and Clear all. Used for
 * the teacher's roster, a new class's allowed students, and editing an
 * existing class's allowed students.
 */
export function StudentPicker({
  students,
  selected,
  onChange,
  loading,
  emptyMessage,
  lockedIds,
  lockedReason,
}: {
  students: StudentSummary[]
  selected: Set<number>
  onChange: (next: Set<number>) => void
  loading?: boolean
  emptyMessage?: string
  // Selected ids that can't be unselected (e.g. while a class is live).
  lockedIds?: Set<number>
  lockedReason?: string
}) {
  const [query, setQuery] = useState('')

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return students
    return students.filter((s) =>
      [s.name, s.email, s.usn].some((v) => v?.toLowerCase().includes(q)),
    )
  }, [students, query])

  const toggle = (id: number) => {
    const next = new Set(selected)
    if (next.has(id)) {
      if (lockedIds?.has(id)) return
      next.delete(id)
    } else {
      next.add(id)
    }
    onChange(next)
  }

  const selectAll = () => {
    const next = new Set(selected)
    visible.forEach((s) => next.add(s.studentId))
    onChange(next)
  }

  const clearAll = () => {
    const next = new Set<number>()
    selected.forEach((id) => {
      if (lockedIds?.has(id)) next.add(id)
    })
    onChange(next)
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[180px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, email or student ID"
            className="pl-9"
            aria-label="Search students"
          />
        </div>
        <Button size="sm" variant="outline" onClick={selectAll} disabled={visible.length === 0}>
          Select all
        </Button>
        <Button size="sm" variant="outline" onClick={clearAll} disabled={selected.size === 0}>
          Clear all
        </Button>
      </div>

      <p className="text-xs text-textmuted-light dark:text-textmuted-dark" data-testid="picker-count">
        {selected.size} of {students.length} selected
        {lockedIds && lockedIds.size > 0 && lockedReason && <> · {lockedReason}</>}
      </p>

      <div className="max-h-72 overflow-y-auto rounded-xl border border-border-light dark:border-border-dark">
        {loading ? (
          <div className="space-y-2 p-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <p className="p-6 text-center text-sm text-textmuted-light dark:text-textmuted-dark">
            {students.length === 0 ? emptyMessage ?? 'No students found.' : 'No students match your search.'}
          </p>
        ) : (
          <ul className="divide-y divide-border-light dark:divide-border-dark">
            {visible.map((s) => {
              const checked = selected.has(s.studentId)
              const locked = checked && lockedIds?.has(s.studentId)
              return (
                <li key={s.studentId}>
                  <label
                    className={cn(
                      'flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-black/5 dark:hover:bg-white/5',
                      locked && 'cursor-not-allowed opacity-80',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={Boolean(locked)}
                      onChange={() => toggle(s.studentId)}
                      className="h-4 w-4 accent-focus-500"
                      aria-label={`Select ${s.name}`}
                    />
                    <Avatar name={s.name} size={30} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-text-light dark:text-text-dark">{s.name}</p>
                      <p className="truncate text-xs text-textmuted-light dark:text-textmuted-dark">
                        {s.usn} · {s.email}
                      </p>
                    </div>
                  </label>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
