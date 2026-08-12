import { cn, initials } from '@/lib/utils'

const RING_COLORS = ['#4F5DFF', '#22C55E', '#F5A524', '#F0466E', '#7C86FF']

function colorFor(seed: string) {
  const idx = seed.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % RING_COLORS.length
  return RING_COLORS[idx]
}

export function Avatar({
  name,
  src,
  size = 36,
  ring,
  className,
}: {
  name: string
  src?: string
  size?: number
  ring?: boolean
  className?: string
}) {
  const color = colorFor(name)
  return (
    <div
      className={cn('relative flex shrink-0 items-center justify-center rounded-full font-display font-semibold text-white', className)}
      style={{
        width: size,
        height: size,
        backgroundColor: color,
        fontSize: size * 0.38,
        boxShadow: ring ? `0 0 0 2px var(--color-surface-light), 0 0 0 4px ${color}` : undefined,
      }}
    >
      {src ? <img src={src} alt={name} className="h-full w-full rounded-full object-cover" /> : initials(name)}
    </div>
  )
}
