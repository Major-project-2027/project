import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border-light px-6 py-14 text-center dark:border-border-dark">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-focus-500/10">
        <Icon className="h-6 w-6 text-focus-500" />
      </div>
      <div>
        <p className="font-display text-sm font-semibold text-text-light dark:text-text-dark">{title}</p>
        {description && <p className="mt-1 max-w-sm text-sm text-textmuted-light dark:text-textmuted-dark">{description}</p>}
      </div>
      {action}
    </div>
  )
}
