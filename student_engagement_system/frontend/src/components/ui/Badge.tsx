import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', {
  variants: {
    variant: {
      neutral: 'bg-black/5 text-textmuted-light dark:bg-white/10 dark:text-textmuted-dark',
      engaged: 'bg-engaged-500/10 text-engaged-600 dark:text-engaged-400',
      attention: 'bg-attention-500/10 text-attention-600 dark:text-attention-400',
      critical: 'bg-critical-500/10 text-critical-600 dark:text-critical-400',
      focus: 'bg-focus-500/10 text-focus-600 dark:text-focus-400',
      outline: 'border border-border-light dark:border-border-dark text-text-light dark:text-text-dark',
    },
  },
  defaultVariants: { variant: 'neutral' },
})

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
