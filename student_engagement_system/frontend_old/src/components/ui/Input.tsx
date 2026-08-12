import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, error, ...props }, ref) => {
  return (
    <div className="w-full">
      <input
        ref={ref}
        className={cn(
          'h-10 w-full rounded-lg border border-border-light bg-surface-light px-3 text-sm text-text-light placeholder:text-textmuted-light/70 outline-none transition-colors focus:border-focus-500 dark:border-border-dark dark:bg-surface-dark dark:text-text-dark dark:placeholder:text-textmuted-dark/60',
          error && 'border-critical-500 focus:border-critical-500',
          className,
        )}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-critical-500">{error}</p>}
    </div>
  )
})
Input.displayName = 'Input'

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn('mb-1.5 block text-sm font-medium text-text-light dark:text-text-dark', className)} {...props} />
}
