import { useCallback, useEffect, useRef, useState } from 'react'
import { Eraser, Pencil, Trash2, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { WhiteboardStroke } from '@/lib/classroomSocket'

const COLORS = ['#111827', '#2563eb', '#dc2626', '#16a34a', '#f59e0b']
const WIDTHS = [2, 4, 8]
const ERASER_WIDTH_FACTOR = 5
// Stroke widths are relative to a 1000px-wide board so they look the same
// at every screen size.
const BASE_WIDTH = 1000
const SEND_INTERVAL_MS = 50
const MAX_POINTS_PER_CHUNK = 40

function drawStroke(ctx: CanvasRenderingContext2D, stroke: WhiteboardStroke, w: number, h: number) {
  if (stroke.points.length === 0) return
  ctx.save()
  ctx.globalCompositeOperation = stroke.mode === 'erase' ? 'destination-out' : 'source-over'
  ctx.strokeStyle = stroke.color
  ctx.fillStyle = stroke.color
  ctx.lineWidth = (stroke.width * w) / BASE_WIDTH
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  const [x0, y0] = stroke.points[0]
  if (stroke.points.length === 1) {
    ctx.beginPath()
    ctx.arc(x0 * w, y0 * h, ctx.lineWidth / 2, 0, Math.PI * 2)
    ctx.fill()
  } else {
    ctx.beginPath()
    ctx.moveTo(x0 * w, y0 * h)
    for (let i = 1; i < stroke.points.length; i++) {
      const [x, y] = stroke.points[i]
      ctx.lineTo(x * w, y * h)
    }
    ctx.stroke()
  }
  ctx.restore()
}

/**
 * Classroom whiteboard. The teacher draws (pen / eraser / colors / widths /
 * clear); students get a read-only view. Strokes are normalized (0..1) and
 * streamed in small chunks over the classroom WebSocket; the parent owns
 * the stroke list (`strokes`, mutated in place, with `strokeCount` /
 * `clearToken` signalling changes) so this component only renders.
 */
export function Whiteboard({
  strokes,
  strokeCount,
  clearToken,
  editable,
  onStroke,
  onClear,
  onClose,
}: {
  strokes: WhiteboardStroke[]
  strokeCount: number
  clearToken: number
  editable: boolean
  onStroke?: (stroke: WhiteboardStroke) => void
  onClear?: () => void
  onClose?: () => void
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const drawnRef = useRef(0)
  const lastClearRef = useRef(clearToken)

  const [mode, setMode] = useState<'pen' | 'erase'>('pen')
  const [color, setColor] = useState(COLORS[0])
  const [width, setWidth] = useState(WIDTHS[1])

  // In-progress stroke (teacher only)
  const drawingRef = useRef<{ id: string; pending: [number, number][]; last: [number, number] | null; timer: number | null } | null>(null)

  const redrawAll = useCallback(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    for (let i = 0; i < strokeCount && i < strokes.length; i++) {
      drawStroke(ctx, strokes[i], canvas.width, canvas.height)
    }
    drawnRef.current = Math.min(strokeCount, strokes.length)
  }, [strokes, strokeCount])

  // Size the canvas to its container (device pixels), redraw on resize.
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return
    const resize = () => {
      const rect = container.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.max(1, Math.round(rect.width * dpr))
      canvas.height = Math.max(1, Math.round(rect.height * dpr))
      redrawAll()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(container)
    resize()
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Incremental draws for new strokes; full clear when clearToken changes.
  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    if (lastClearRef.current !== clearToken) {
      lastClearRef.current = clearToken
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      drawnRef.current = 0
    }
    if (strokeCount < drawnRef.current) {
      redrawAll()
      return
    }
    for (let i = drawnRef.current; i < strokeCount && i < strokes.length; i++) {
      drawStroke(ctx, strokes[i], canvas.width, canvas.height)
    }
    drawnRef.current = Math.min(strokeCount, strokes.length)
  }, [strokes, strokeCount, clearToken, redrawAll])

  const toPoint = (e: React.PointerEvent): [number, number] => {
    const rect = canvasRef.current!.getBoundingClientRect()
    return [
      Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1),
      Math.min(Math.max((e.clientY - rect.top) / rect.height, 0), 1),
    ]
  }

  const flush = () => {
    const d = drawingRef.current
    if (!d || d.pending.length === 0) return
    const stroke: WhiteboardStroke = {
      id: d.id,
      // Each chunk starts at the previous chunk's last point so the line
      // stays continuous for viewers.
      points: d.last ? [d.last, ...d.pending] : [...d.pending],
      width: mode === 'erase' ? width * ERASER_WIDTH_FACTOR : width,
      color,
      mode,
    }
    d.last = d.pending[d.pending.length - 1]
    d.pending = []
    onStroke?.(stroke)
  }

  const onPointerDown = (e: React.PointerEvent) => {
    if (!editable) return
    e.currentTarget.setPointerCapture(e.pointerId)
    drawingRef.current = {
      id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`,
      pending: [toPoint(e)],
      last: null,
      timer: window.setInterval(flush, SEND_INTERVAL_MS),
    }
  }

  const onPointerMove = (e: React.PointerEvent) => {
    const d = drawingRef.current
    if (!editable || !d) return
    d.pending.push(toPoint(e))
    if (d.pending.length >= MAX_POINTS_PER_CHUNK) flush()
  }

  const endStroke = () => {
    const d = drawingRef.current
    if (!d) return
    flush()
    if (d.timer) window.clearInterval(d.timer)
    drawingRef.current = null
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden rounded-2xl bg-[#12151f]">
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
        <p className="text-sm font-semibold text-white">
          Whiteboard
          {!editable && <span className="ml-2 text-xs font-normal text-white/50">View only</span>}
        </p>

        {editable && (
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setMode('pen')}
              aria-label="Pen"
              title="Pen"
              className={cn('flex h-8 w-8 items-center justify-center rounded-lg text-white/80 hover:bg-white/10', mode === 'pen' && 'bg-white/15 text-white')}
            >
              <Pencil className="h-4 w-4" />
            </button>
            <button
              onClick={() => setMode('erase')}
              aria-label="Eraser"
              title="Eraser"
              className={cn('flex h-8 w-8 items-center justify-center rounded-lg text-white/80 hover:bg-white/10', mode === 'erase' && 'bg-white/15 text-white')}
            >
              <Eraser className="h-4 w-4" />
            </button>

            <div className="mx-1 h-5 w-px bg-white/10" />

            {COLORS.map((c) => (
              <button
                key={c}
                onClick={() => {
                  setColor(c)
                  setMode('pen')
                }}
                aria-label={`Color ${c}`}
                className={cn('h-6 w-6 rounded-full ring-2 ring-offset-2 ring-offset-[#12151f]', color === c && mode === 'pen' ? 'ring-white' : 'ring-transparent')}
                style={{ backgroundColor: c }}
              />
            ))}

            <div className="mx-1 h-5 w-px bg-white/10" />

            {WIDTHS.map((w) => (
              <button
                key={w}
                onClick={() => setWidth(w)}
                aria-label={`Line width ${w}`}
                title={`Line width ${w}`}
                className={cn('flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10', width === w && 'bg-white/15')}
              >
                <span className="rounded-full bg-white" style={{ width: w + 2, height: w + 2 }} />
              </button>
            ))}

            <div className="mx-1 h-5 w-px bg-white/10" />

            <button
              onClick={onClear}
              aria-label="Clear board"
              title="Clear board"
              className="flex h-8 items-center gap-1 rounded-lg px-2 text-xs text-white/80 hover:bg-white/10"
            >
              <Trash2 className="h-4 w-4" />
              Clear
            </button>
            <button
              onClick={onClose}
              aria-label="Close whiteboard"
              title="Close whiteboard"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-white/80 hover:bg-white/10"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-1 items-center justify-center p-3">
        <div ref={containerRef} className="relative aspect-video max-h-full w-full max-w-full rounded-xl bg-white">
          <canvas
            ref={canvasRef}
            data-testid="whiteboard-canvas"
            className={cn('absolute inset-0 h-full w-full touch-none rounded-xl', editable ? (mode === 'erase' ? 'cursor-cell' : 'cursor-crosshair') : 'cursor-default')}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endStroke}
            onPointerCancel={endStroke}
            onPointerLeave={endStroke}
          />
        </div>
      </div>
    </div>
  )
}
