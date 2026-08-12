import { cn } from '@/lib/utils'

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: { value: T; label: string; count?: number }[]
  active: T
  onChange: (v: T) => void
  className?: string
}) {
  return (
    <div className={cn('flex items-center gap-1 rounded-lg bg-black/5 p-1 dark:bg-white/5', className)}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
            active === tab.value
              ? 'bg-surface-light text-text-light shadow-sm dark:bg-surface-dark dark:text-text-dark'
              : 'text-textmuted-light hover:text-text-light dark:text-textmuted-dark dark:hover:text-text-dark',
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className="rounded-full bg-black/8 px-1.5 text-xs dark:bg-white/10">{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}
