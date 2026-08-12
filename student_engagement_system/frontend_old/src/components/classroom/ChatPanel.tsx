import { useState } from 'react'
import { Send } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'

interface ChatMessage {
  id: string
  author: string
  message: string
  time: string
  self?: boolean
}

const seed: ChatMessage[] = [
  { id: '1', author: 'Dr. Kavita Rao', message: 'Welcome everyone — we\'ll start with a quick recap of backpropagation.', time: '09:01' },
  { id: '2', author: 'Isha Reddy', message: 'Could you share the slides after class?', time: '09:04' },
  { id: '3', author: 'Dr. Kavita Rao', message: 'Yes, they\'ll be posted right after.', time: '09:05' },
]

export function ChatPanel() {
  const [messages, setMessages] = useState(seed)
  const [draft, setDraft] = useState('')

  const send = () => {
    if (!draft.trim()) return
    setMessages((m) => [...m, { id: String(Date.now()), author: 'You', message: draft, time: 'now', self: true }])
    setDraft('')
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-4 py-3">
        <p className="text-sm font-semibold text-white">Class chat</p>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.map((m) => (
          <div key={m.id} className="flex items-start gap-2">
            {!m.self && <Avatar name={m.author} size={26} />}
            <div className={m.self ? 'ml-auto max-w-[80%] text-right' : 'max-w-[80%]'}>
              {!m.self && <p className="text-[11px] font-medium text-white/60">{m.author} · {m.time}</p>}
              <p className={`mt-0.5 inline-block rounded-xl px-3 py-1.5 text-sm ${m.self ? 'bg-focus-500 text-white' : 'bg-white/10 text-white'}`}>{m.message}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 border-t border-white/10 p-3">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Send a message"
          className="h-9 flex-1 rounded-lg bg-white/10 px-3 text-sm text-white placeholder:text-white/40 outline-none focus:ring-1 focus:ring-focus-500"
        />
        <button onClick={send} className="flex h-9 w-9 items-center justify-center rounded-lg bg-focus-500 text-white">
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
