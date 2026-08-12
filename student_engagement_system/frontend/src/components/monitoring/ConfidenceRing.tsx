import { cn, engagementTone } from '@/lib/utils'

const TONE_COLOR = {
  engaged: '#22C55E',
  attention: '#F5A524',
  critical: '#F0466E',
} as const

export function ConfidenceRing({
  value,
  size = 64,
  strokeWidth = 6,
  label,
  toneOverride,
  className,
}: {
  value: number // 0-100
  size?: number
  strokeWidth?: number
  label?: string
  toneOverride?: keyof typeof TONE_COLOR
  className?: string
}) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (value / 100) * circumference
  const tone = toneOverride ?? engagementTone(value)
  const color = TONE_COLOR[tone]

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-black/8 dark:stroke-white/10"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.6s cubic-bezier(0.16,1,0.3,1)' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="font-mono text-sm font-semibold text-text-light dark:text-text-dark">{Math.round(value)}</span>
        {label && <span className="text-[9px] uppercase tracking-wide text-textmuted-light dark:text-textmuted-dark">{label}</span>}
      </div>
    </div>
  )
}

/** The "Focus Pulse" — an animated heartbeat-style line, the signature visual
 * motif of the platform, used wherever live attention/engagement is implied. */
export function FocusPulse({ active = true, className }: { active?: boolean; className?: string }) {
  const bars = [0.4, 0.7, 1, 0.55, 0.85, 0.35, 0.65]
  return (
    <div className={cn('flex h-4 items-end gap-[3px]', className)} aria-hidden>
      {bars.map((h, i) => (
        <span
          key={i}
          className={cn('w-[3px] rounded-full bg-focus-500', active && 'animate-pulse-line')}
          style={{ height: `${h * 100}%`, animationDelay: `${i * 0.09}s` }}
        />
      ))}
    </div>
  )
}
