import { useEffect, useRef, useState } from 'react'
import { Send } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import type { ClassChatMessage } from '@/lib/classroomSocket'

function formatTime(ts: string) {
  const d = new Date(ts)
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * Real-time classroom chat. Messages arrive over the classroom WebSocket
 * (server-stamped sender name/role/time, scoped to this class); this
 * component only renders them and hands new text to `onSend`.
 */
export function ChatPanel({
  messages,
  selfKey,
  onSend,
  disabled,
}: {
  messages: ClassChatMessage[]
  selfKey: string | null
  onSend: (text: string) => void
  disabled?: boolean
}) {
  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages.length])

  const send = () => {
    const text = draft.trim()
    if (!text || disabled) return
    onSend(text)
    setDraft('')
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-4 py-3">
        <p className="text-sm font-semibold text-white">Class chat</p>
        <p className="mt-0.5 text-[11px] text-white/40">Visible to everyone in this class</p>
      </div>

      <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.length === 0 && (
          <p className="pt-6 text-center text-xs text-white/40">No messages yet</p>
        )}
        {messages.map((m) => {
          const self = m.senderKey === selfKey
          return (
            <div key={m.id} className="flex items-start gap-2">
              {!self && <Avatar name={m.senderName} size={26} />}
              <div className={self ? 'ml-auto max-w-[80%] text-right' : 'max-w-[80%]'}>
                <p className="text-[11px] font-medium text-white/60">
                  {self ? 'You' : m.senderName}
                  {m.senderRole === 'teacher' && (
                    <span className="ml-1 rounded bg-focus-500/30 px-1 text-[10px] text-focus-200">Teacher</span>
                  )}
                  <span className="text-white/40"> · {formatTime(m.ts)}</span>
                </p>
                <p
                  className={`mt-0.5 inline-block whitespace-pre-wrap break-words rounded-xl px-3 py-1.5 text-left text-sm ${
                    self ? 'bg-focus-500 text-white' : 'bg-white/10 text-white'
                  }`}
                >
                  {m.text}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center gap-2 border-t border-white/10 p-3">
        <input
          value={draft}
          maxLength={1000}
          disabled={disabled}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder={disabled ? 'Connecting…' : 'Send a message'}
          aria-label="Chat message"
          className="h-9 flex-1 rounded-lg bg-white/10 px-3 text-sm text-white placeholder:text-white/40 outline-none focus:ring-1 focus:ring-focus-500 disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={disabled || !draft.trim()}
          aria-label="Send message"
          className="flex h-9 w-9 items-center justify-center rounded-lg bg-focus-500 text-white disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
