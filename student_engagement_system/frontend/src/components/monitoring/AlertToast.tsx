import { useEffect, useState, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, X } from 'lucide-react'

export interface ToastItem {
  id: string
  studentName: string
  message: string
  severity: 'warning' | 'critical'
  // When true, plays a single short alert tone the moment this toast is
  // raised (not on every render/poll -- pushAlertToast is itself only
  // ever called once per newly-detected alert, see the caller in
  // TeacherLiveClassroomPage.tsx, so "once per toast" already means
  // "once per continuous episode"). Opt-in per toast rather than global,
  // so existing alert types that never asked for a sound stay silent.
  sound?: boolean
}

let pushToastImpl: ((t: Omit<ToastItem, 'id'>) => void) | null = null

/** Call from anywhere to raise a live alert toast (e.g. when the mock
 * monitoring stream detects a new attention/behavior issue). */
export function pushAlertToast(toast: Omit<ToastItem, 'id'>) {
  pushToastImpl?.(toast)
}

// No audio mechanism existed anywhere else in the frontend (checked
// before adding this). A short synthesized two-beep tone via the
// standard Web Audio API -- no new audio asset file, no new library --
// kept intentionally small since it only ever needs to fire once per
// alert toast.
function playAlertTone() {
  try {
    const Ctx = window.AudioContext || (window as any).webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const now = ctx.currentTime

    ;[0, 0.18].forEach((offset) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = 880
      gain.gain.setValueAtTime(0.0001, now + offset)
      gain.gain.exponentialRampToValueAtTime(0.3, now + offset + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.16)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(now + offset)
      osc.stop(now + offset + 0.17)
    })

    setTimeout(() => ctx.close().catch(() => {}), 600)
  } catch {
    // Audio is a non-essential enhancement -- never let it break alerting.
  }
}

export function AlertToastStack() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  useEffect(() => {
    pushToastImpl = (toast) => {
      const id = `${Date.now()}-${Math.random()}`
      if (toast.sound) {
        playAlertTone()
      }
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
