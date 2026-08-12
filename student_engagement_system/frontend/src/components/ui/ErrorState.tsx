import { AlertTriangle } from 'lucide-react'
import { Button } from './Button'

export function ErrorState({ message = 'Something went wrong while loading this data.', onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-critical-500/20 bg-critical-500/5 px-6 py-14 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-critical-500/10">
        <AlertTriangle className="h-6 w-6 text-critical-500" />
      </div>
      <div>
        <p className="font-display text-sm font-semibold text-text-light dark:text-text-dark">Couldn't load this</p>
        <p className="mt-1 max-w-sm text-sm text-textmuted-light dark:text-textmuted-dark">{message}</p>
      </div>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>}
    </div>
  )
}
