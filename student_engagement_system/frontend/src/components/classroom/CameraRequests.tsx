import { useState } from 'react'
import { Check, VideoOff, X } from 'lucide-react'
import { CAMERA_OFF_REASONS, type CameraOffRequest } from '@/lib/classroomSocket'
import { cn } from '@/lib/utils'

function formatTime(ts: string) {
  const date = new Date(ts)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * Student: ask the teacher for permission to turn the camera off. Closing
 * or cancelling sends nothing -- the camera just stays on.
 */
export function CameraOffRequestModal({
  onSubmit,
  onClose,
}: {
  onSubmit: (reason: string, note: string) => void
  onClose: () => void
}) {
  const [reason, setReason] = useState<string>(CAMERA_OFF_REASONS[0])
  const [note, setNote] = useState('')

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="camera-off-request-title"
      onClick={onClose}
    >
      <form
        className="w-full max-w-sm rounded-2xl bg-[#171923] p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit(reason, reason === 'Other' ? note.trim() : '')
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <VideoOff className="h-5 w-5 text-attention-400" />
            <p id="camera-off-request-title" className="text-base font-semibold text-white">
              Camera Off Request
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-white/40 hover:text-white" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mt-2 text-sm text-white/60">
          Your camera must stay on during class. Your teacher will approve or reject this request.
        </p>

        <fieldset className="mt-4 space-y-1.5">
          <legend className="mb-1 text-xs font-medium text-white/50">Reason</legend>
          {CAMERA_OFF_REASONS.map((option) => (
            <label
              key={option}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-white/80 hover:bg-white/5',
                reason === option && 'bg-white/10 text-white',
              )}
            >
              <input
                type="radio"
                name="camera-off-reason"
                value={option}
                checked={reason === option}
                onChange={() => setReason(option)}
                className="accent-focus-500"
              />
              {option}
            </label>
          ))}
        </fieldset>

        {reason === 'Other' && (
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={200}
            rows={2}
            placeholder="Briefly describe the reason"
            className="mt-2 w-full resize-none rounded-lg bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-focus-500"
          />
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-white/70 hover:bg-white/10">
            Cancel
          </button>
          <button
            type="submit"
            disabled={reason === 'Other' && !note.trim()}
            className="rounded-lg bg-focus-500 px-4 py-2 text-sm font-medium text-white hover:bg-focus-600 disabled:opacity-40"
          >
            Send request
          </button>
        </div>
      </form>
    </div>
  )
}

/** Teacher: pending camera-off requests with Approve / Reject. */
export function CameraRequestsPanel({
  requests,
  onDecide,
}: {
  requests: CameraOffRequest[]
  onDecide: (id: string, approve: boolean) => void
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-4 py-3">
        <p className="text-sm font-semibold text-white">Camera requests</p>
        <p className="text-xs text-white/50">Students need your approval to turn their camera off.</p>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {requests.length === 0 && (
          <p className="mt-6 text-center text-sm text-white/40">No pending requests.</p>
        )}

        {requests.map((request) => (
          <div
            key={request.id}
            className="rounded-xl border border-attention-500/30 bg-attention-500/10 p-3"
            data-testid="camera-request"
          >
            <div className="flex items-baseline justify-between gap-2">
              <p className="truncate text-sm font-medium text-white">{request.studentName}</p>
              <span className="shrink-0 text-[11px] text-white/50">{formatTime(request.ts)}</span>
            </div>
            <p className="mt-0.5 text-xs text-attention-400">{request.reason}</p>
            {request.note && <p className="mt-1 break-words text-xs text-white/70">{request.note}</p>}

            <div className="mt-2.5 flex gap-2">
              <button
                onClick={() => onDecide(request.id, true)}
                className="flex flex-1 items-center justify-center gap-1 rounded-lg bg-engaged-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-engaged-600"
              >
                <Check className="h-3.5 w-3.5" />
                Approve
              </button>
              <button
                onClick={() => onDecide(request.id, false)}
                className="flex flex-1 items-center justify-center gap-1 rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/20"
              >
                <X className="h-3.5 w-3.5" />
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
