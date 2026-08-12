import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  GraduationCap, ScanFace, Eye, Brain, Activity, ShieldCheck,
  ArrowRight, Video, BarChart3, Bell,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { FocusPulse, ConfidenceRing } from '@/components/monitoring/ConfidenceRing'
import { useTheme } from '@/context/ThemeContext'
import { Moon, Sun } from 'lucide-react'

const capabilities = [
  { icon: ScanFace, title: 'Face authentication', desc: 'Every session starts by verifying identity, so engagement data always maps to the right student.' },
  { icon: Eye, title: 'Gaze & head pose', desc: 'MediaPipe-based tracking flags when attention drifts off-screen before it becomes a pattern.' },
  { icon: Brain, title: 'Emotion recognition', desc: 'CNN-based models read frustration, confusion, and boredom as they happen, not after the test.' },
  { icon: Activity, title: 'Predictive engagement', desc: 'An LSTM model forecasts attention drops minutes ahead, so teachers can act before it happens.' },
]

const steps = [
  { label: 'Join', desc: 'Students authenticate and enter the live classroom in one step.' },
  { label: 'Monitor', desc: 'Six AI models continuously read behavior across video and audio.' },
  { label: 'Alert', desc: 'Teachers see live scores and get notified the moment something needs attention.' },
  { label: 'Report', desc: 'Every session becomes a trend line — attendance, focus, and behavior over time.' },
]

export function LandingPage() {
  const { theme, toggleTheme } = useTheme()
  return (
    <div className="min-h-screen bg-bg-light dark:bg-bg-dark">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-focus-500 text-white">
            <GraduationCap className="h-5 w-5" />
          </div>
          <span className="font-display text-lg font-bold text-text-light dark:text-text-dark">Cognivue</span>
        </div>
        <nav className="hidden items-center gap-8 md:flex">
          <a href="#capabilities" className="text-sm font-medium text-textmuted-light hover:text-text-light dark:text-textmuted-dark dark:hover:text-text-dark">Capabilities</a>
          <a href="#flow" className="text-sm font-medium text-textmuted-light hover:text-text-light dark:text-textmuted-dark dark:hover:text-text-dark">How it works</a>
          <Link to="/about" className="text-sm font-medium text-textmuted-light hover:text-text-light dark:text-textmuted-dark dark:hover:text-text-dark">About</Link>
        </nav>
        <div className="flex items-center gap-2">
          <button onClick={toggleTheme} className="flex h-9 w-9 items-center justify-center rounded-lg text-textmuted-light hover:bg-black/5 dark:text-textmuted-dark dark:hover:bg-white/10">
            {theme === 'dark' ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
          </button>
          <Link to="/login"><Button variant="ghost" size="sm">Sign in</Button></Link>
          <Link to="/register"><Button size="sm">Get started</Button></Link>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto grid max-w-7xl gap-12 px-6 pb-20 pt-10 md:grid-cols-2 md:items-center md:pt-16">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border-light px-3 py-1 text-xs font-medium text-textmuted-light dark:border-border-dark dark:text-textmuted-dark">
            <FocusPulse className="h-3" />
            Live engagement intelligence for virtual classrooms
          </div>
          <h1 className="font-display text-4xl font-bold leading-[1.1] tracking-tight text-text-light dark:text-text-dark md:text-5xl">
            See attention the way a classroom teacher would — at scale, in real time.
          </h1>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-textmuted-light dark:text-textmuted-dark">
            Cognivue reads facial expression, gaze, posture, and voice across every student in a live session,
            turning it into one engagement score, predictive alerts, and reports that actually explain what happened.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to="/register"><Button size="lg">Create free account <ArrowRight className="h-4 w-4" /></Button></Link>
            <Link to="/login"><Button size="lg" variant="secondary">I already have an account</Button></Link>
          </div>
          <div className="mt-10 flex items-center gap-6 text-sm text-textmuted-light dark:text-textmuted-dark">
            <div><span className="font-display text-xl font-bold text-text-light dark:text-text-dark">6</span> AI models running live</div>
            <div><span className="font-display text-xl font-bold text-text-light dark:text-text-dark">0–100</span> engagement scoring</div>
            <div><span className="font-display text-xl font-bold text-text-light dark:text-text-dark">±5 min</span> predictive window</div>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, delay: 0.1 }} className="relative">
          <div className="rounded-3xl border border-border-light bg-surface-light p-4 shadow-2xl dark:border-border-dark dark:bg-surface-dark">
            <div className="mb-3 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-medium text-critical-500"><span className="h-2 w-2 rounded-full bg-critical-500 animate-pulse" />LIVE · Machine Learning</span>
              <span className="text-xs text-textmuted-light dark:text-textmuted-dark">32 students</span>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex aspect-video items-center justify-center rounded-lg bg-focus-500/10">
                  <Video className="h-4 w-4 text-focus-400" />
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center justify-between rounded-xl bg-bg-light p-3 dark:bg-bg-dark">
              <div className="flex items-center gap-3">
                <ConfidenceRing value={78} size={48} strokeWidth={5} />
                <div>
                  <p className="text-sm font-semibold text-text-light dark:text-text-dark">Class engagement</p>
                  <p className="text-xs text-textmuted-light dark:text-textmuted-dark">Trending up over last 10 min</p>
                </div>
              </div>
              <BarChart3 className="h-5 w-5 text-textmuted-light dark:text-textmuted-dark" />
            </div>
          </div>
          <div className="absolute -bottom-4 -left-4 flex items-center gap-2 rounded-xl border border-border-light bg-surface-light px-3 py-2 shadow-lg dark:border-border-dark dark:bg-surface-dark">
            <Bell className="h-4 w-4 text-attention-500" />
            <span className="text-xs font-medium text-text-light dark:text-text-dark">Attention drop predicted — Row 3</span>
          </div>
        </motion.div>
      </section>

      {/* Capabilities */}
      <section id="capabilities" className="border-y border-border-light bg-surface-light py-20 dark:border-border-dark dark:bg-surface-dark">
        <div className="mx-auto max-w-7xl px-6">
          <h2 className="font-display text-2xl font-bold text-text-light dark:text-text-dark md:text-3xl">Six models, one engagement score</h2>
          <p className="mt-2 max-w-xl text-textmuted-light dark:text-textmuted-dark">Every capability below is already trained and running — the platform composes them into a single live signal for teachers.</p>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {capabilities.map((c) => (
              <div key={c.title} className="rounded-2xl border border-border-light p-5 dark:border-border-dark">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-focus-500/10">
                  <c.icon className="h-5 w-5 text-focus-500" />
                </div>
                <h3 className="font-display text-sm font-semibold text-text-light dark:text-text-dark">{c.title}</h3>
                <p className="mt-1.5 text-sm text-textmuted-light dark:text-textmuted-dark">{c.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Flow */}
      <section id="flow" className="mx-auto max-w-7xl px-6 py-20">
        <h2 className="font-display text-2xl font-bold text-text-light dark:text-text-dark md:text-3xl">From join to report, in one flow</h2>
        <div className="mt-10 grid gap-6 md:grid-cols-4">
          {steps.map((s, i) => (
            <div key={s.label} className="relative">
              <div className="mb-3 font-mono text-xs text-focus-500">{String(i + 1).padStart(2, '0')}</div>
              <h3 className="font-display text-base font-semibold text-text-light dark:text-text-dark">{s.label}</h3>
              <p className="mt-1.5 text-sm text-textmuted-light dark:text-textmuted-dark">{s.desc}</p>
              {i < steps.length - 1 && <div className="absolute right-[-12px] top-1.5 hidden h-px w-6 bg-border-light dark:bg-border-dark md:block" />}
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-6 pb-24">
        <div className="flex flex-col items-center justify-between gap-6 rounded-3xl bg-focus-500 px-8 py-12 text-center md:flex-row md:text-left">
          <div>
            <h2 className="font-display text-2xl font-bold text-white">Bring real classroom awareness to your online sessions</h2>
            <p className="mt-2 text-focus-100">Set up your first live class in minutes.</p>
          </div>
          <Link to="/register"><Button size="lg" variant="secondary" className="whitespace-nowrap">Create free account</Button></Link>
        </div>
      </section>

      <footer className="border-t border-border-light py-8 dark:border-border-dark">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 text-sm text-textmuted-light dark:text-textmuted-dark md:flex-row">
          <span>© 2026 Cognivue. Final-year engineering project, BIT — Dept. of CSE.</span>
          <div className="flex items-center gap-5">
            <Link to="/about" className="hover:text-text-light dark:hover:text-text-dark">About</Link>
            <Link to="/help" className="hover:text-text-light dark:hover:text-text-dark">Help</Link>
            <Link to="/support" className="hover:text-text-light dark:hover:text-text-dark">Support</Link>
            <ShieldCheck className="h-4 w-4" />
          </div>
        </div>
      </footer>
    </div>
  )
}
