import type { LucideIcon } from 'lucide-react'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { cn } from '@/lib/utils'

export function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  tone = 'focus',
}: {
  label: string
  value: string
  icon: LucideIcon
  trend?: { value: number; positive: boolean }
  tone?: 'focus' | 'engaged' | 'attention' | 'critical'
}) {
  const toneClasses = {
    focus: 'bg-focus-500/10 text-focus-500',
    engaged: 'bg-engaged-500/10 text-engaged-500',
    attention: 'bg-attention-500/10 text-attention-500',
    critical: 'bg-critical-500/10 text-critical-500',
  }
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-textmuted-light dark:text-textmuted-dark">{label}</p>
          <p className="mt-2 font-display text-2xl font-bold text-text-light dark:text-text-dark">{value}</p>
        </div>
        <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', toneClasses[tone])}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      {trend && (
        <div className={cn('mt-3 flex items-center gap-1 text-xs font-medium', trend.positive ? 'text-engaged-600 dark:text-engaged-400' : 'text-critical-600 dark:text-critical-400')}>
          {trend.positive ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
          {trend.value}% vs last week
        </div>
      )}
    </Card>
  )
}
