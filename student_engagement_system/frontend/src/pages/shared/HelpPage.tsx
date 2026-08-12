import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, Search, GraduationCap } from 'lucide-react'
import { cn } from '@/lib/utils'

const faqs = [
  { q: 'How does face authentication work?', a: 'Before a monitored session begins, the platform captures a short video frame, encodes facial features, and matches them against your enrolled profile. If verification fails, you can retry or contact your teacher.' },
  { q: 'What happens if I turn my camera off during class?', a: 'If your teacher requires cameras for a session, turning it off is flagged and your teacher is notified. If camera use is optional, no alert is generated.' },
  { q: 'How is the engagement score calculated?', a: 'It combines attention (gaze and head pose), emotion, participation, and a distraction penalty into a single 0–100 score, updated continuously during a live session.' },
  { q: 'Can I dispute an AI alert?', a: 'Yes. Every alert includes a confidence score and timestamp. You can flag it as incorrect from the Notifications page, and it will be reviewed by your teacher or administrator.' },
  { q: 'Is my video stored or recorded?', a: 'Only metadata derived from the AI models (scores, alerts, emotions) is stored by default. Video recording only happens if your teacher explicitly enables it for a session.' },
]

export function HelpPage() {
  const [open, setOpen] = useState<number | null>(0)
  const [query, setQuery] = useState('')
  const filtered = faqs.filter((f) => f.q.toLowerCase().includes(query.toLowerCase()))

  return (
    <div className="min-h-screen bg-bg-light dark:bg-bg-dark">
      <header className="mx-auto flex max-w-3xl items-center gap-2 px-6 py-6">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-focus-500 text-white"><GraduationCap className="h-4 w-4" /></div>
          <span className="font-display text-sm font-bold text-text-light dark:text-text-dark">Cognivue</span>
        </Link>
      </header>
      <div className="mx-auto max-w-3xl px-6 pb-20">
        <h1 className="font-display text-3xl font-bold text-text-light dark:text-text-dark">Help Center</h1>
        <p className="mt-2 text-textmuted-light dark:text-textmuted-dark">Answers to common questions about monitoring, privacy, and classroom features.</p>

        <div className="relative mt-6">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search help articles"
            className="h-11 w-full rounded-xl border border-border-light bg-surface-light pl-10 pr-4 text-sm outline-none focus:border-focus-500 dark:border-border-dark dark:bg-surface-dark"
          />
        </div>

        <div className="mt-6 divide-y divide-border-light rounded-2xl border border-border-light dark:divide-border-dark dark:border-border-dark">
          {filtered.map((f, i) => (
            <div key={f.q}>
              <button onClick={() => setOpen(open === i ? null : i)} className="flex w-full items-center justify-between px-5 py-4 text-left">
                <span className="text-sm font-medium text-text-light dark:text-text-dark">{f.q}</span>
                <ChevronDown className={cn('h-4 w-4 shrink-0 text-textmuted-light transition-transform dark:text-textmuted-dark', open === i && 'rotate-180')} />
              </button>
              {open === i && <p className="px-5 pb-4 text-sm text-textmuted-light dark:text-textmuted-dark">{f.a}</p>}
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-sm text-textmuted-light dark:text-textmuted-dark">
          Can't find what you need? <Link to="/support" className="font-medium text-focus-500 hover:underline">Contact support</Link>
        </p>
      </div>
    </div>
  )
}
