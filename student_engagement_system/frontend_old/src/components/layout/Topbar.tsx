import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Moon, Sun, Search, Menu } from 'lucide-react'
import { useTheme } from '@/context/ThemeContext'
import { Avatar } from '@/components/ui/Avatar'
import { useAppSelector } from '@/hooks/useAppStore'
import { cn } from '@/lib/utils'

export function Topbar({ title, onMenuClick }: { title: string; onMenuClick?: () => void }) {
  const { theme, toggleTheme } = useTheme()
  const user = useAppSelector((s) => s.auth.user)
  const [profileOpen, setProfileOpen] = useState(false)

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border-light bg-surface-light/80 px-4 backdrop-blur md:px-6 dark:border-border-dark dark:bg-surface-dark/80">
      <button onClick={onMenuClick} className="rounded-lg p-2 text-textmuted-light hover:bg-black/5 dark:text-textmuted-dark dark:hover:bg-white/10 md:hidden">
        <Menu className="h-5 w-5" />
      </button>
      <h1 className="font-display text-base font-semibold text-text-light dark:text-text-dark md:text-lg">{title}</h1>

      <div className="ml-auto flex items-center gap-2">
        <div className="relative hidden md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-textmuted-light dark:text-textmuted-dark" />
          <input
            placeholder="Search classes, students..."
            className="h-9 w-64 rounded-lg border border-border-light bg-bg-light pl-9 pr-3 text-sm outline-none focus:border-focus-500 dark:border-border-dark dark:bg-bg-dark"
          />
        </div>

        <button
          onClick={toggleTheme}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-textmuted-light hover:bg-black/5 dark:text-textmuted-dark dark:hover:bg-white/10"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
        </button>

        <Link
          to={user?.role === 'teacher' ? '/teacher/notifications' : '/student/notifications'}
          className="relative flex h-9 w-9 items-center justify-center rounded-lg text-textmuted-light hover:bg-black/5 dark:text-textmuted-dark dark:hover:bg-white/10"
        >
          <Bell className="h-[18px] w-[18px]" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-critical-500" />
        </Link>

        <div className="relative">
          <button onClick={() => setProfileOpen((v) => !v)} className="flex items-center gap-2 rounded-lg p-1 hover:bg-black/5 dark:hover:bg-white/10">
            <Avatar name={user?.name ?? 'Guest User'} size={32} />
          </button>
          {profileOpen && (
            <div
              className={cn(
                'absolute right-0 top-11 w-48 rounded-xl border border-border-light bg-surface-light p-1.5 shadow-lg dark:border-border-dark dark:bg-surface-dark',
              )}
              onMouseLeave={() => setProfileOpen(false)}
            >
              <p className="px-3 py-2 text-sm font-medium text-text-light dark:text-text-dark">{user?.name}</p>
              <Link to={user?.role === 'teacher' ? '/teacher/profile' : '/student/profile'} className="block rounded-lg px-3 py-2 text-sm text-textmuted-light hover:bg-black/5 dark:text-textmuted-dark dark:hover:bg-white/10">Profile</Link>
              <Link to="/login" className="block rounded-lg px-3 py-2 text-sm text-critical-500 hover:bg-critical-500/10">Sign out</Link>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
