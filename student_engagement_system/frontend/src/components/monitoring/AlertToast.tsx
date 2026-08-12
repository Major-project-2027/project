import { useEffect, useState, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, X } from 'lucide-react'

export interface ToastItem {
  id: string
  studentName: string
  message: string
  severity: 'warning' | 'critical'
}

let pushToastImpl: ((t: Omit<ToastItem, 'id'>) => void) | null = null

/** Call from anywhere to raise a live alert toast (e.g. when the mock
 * monitoring stream detects a new attention/behavior issue). */
export function pushAlertToast(toast: Omit<ToastItem, 'id'>) {
  pushToastImpl?.(toast)
}

export function AlertToastStack() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  useEffect(() => {
    pushToastImpl = (toast) => {
      const id = `${Date.now()}-${Math.random()}`
      setToasts((t) => [...t, { ...toast, id }].slice(-4))
      setTimeout(() => dismiss(id), 6000)
    }
    return () => { pushToastImpl = null }
  }, [dismiss])

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[60] flex w-80 flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            className={`pointer-events-auto flex items-start gap-2.5 rounded-xl border p-3 shadow-xl backdrop-blur ${
              t.severity === 'critical' ? 'border-critical-500/30 bg-critical-500/15' : 'border-attention-500/30 bg-attention-500/15'
            }`}
          >
            <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${t.severity === 'critical' ? 'text-critical-400' : 'text-attention-400'}`} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-white">{t.studentName}</p>
              <p className="text-xs text-white/70">{t.message}</p>
            </div>
            <button onClick={() => dismiss(t.id)} className="text-white/50 hover:text-white"><X className="h-3.5 w-3.5" /></button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
