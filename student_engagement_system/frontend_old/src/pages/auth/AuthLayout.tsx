import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { GraduationCap } from 'lucide-react'
import type { ReactNode } from 'react'

/**
 * Deliberately minimal — a single centered card, similar to Google's own
 * sign-in page. No marketing panel, no testimonials, no feature grid.
 */
export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-light px-4 py-12 dark:bg-bg-dark">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="w-full max-w-sm rounded-2xl border border-border-light bg-surface-light p-8 shadow-sm dark:border-border-dark dark:bg-surface-dark"
      >
        <Link to="/" className="mb-6 flex items-center justify-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-focus-500 text-white">
            <GraduationCap className="h-5 w-5" />
          </div>
          <span className="font-display text-lg font-bold text-text-light dark:text-text-dark">Cognivue</span>
        </Link>

        <h1 className="text-center font-display text-xl font-semibold text-text-light dark:text-text-dark">{title}</h1>
        <p className="mt-1 text-center text-sm text-textmuted-light dark:text-textmuted-dark">{subtitle}</p>

        <div className="mt-6">{children}</div>
      </motion.div>
    </div>
  )
}
