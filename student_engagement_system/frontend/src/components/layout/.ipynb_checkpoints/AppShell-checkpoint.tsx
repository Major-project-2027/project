import { type ReactNode, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import type { UserRole } from '@/types/domain'
import { navForRole, supportNav } from '@/constants/navigation'
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { X } from 'lucide-react'

export function AppShell({ role, title, children }: { role: UserRole; title: string; children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-bg-light dark:bg-bg-dark">
      <Sidebar role={role} />

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
            <motion.div
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'tween', duration: 0.2 }}
              className="relative z-10 flex h-full w-64 flex-col bg-surface-light p-3 dark:bg-surface-dark"
            >
              <button onClick={() => setMobileOpen(false)} className="mb-2 ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-textmuted-light hover:bg-black/5">
                <X className="h-4 w-4" />
              </button>
              {[...navForRole(role), ...supportNav].map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium',
                      isActive ? 'bg-focus-500/10 text-focus-600' : 'text-textmuted-light dark:text-textmuted-dark',
                    )
                  }
                >
                  <item.icon className="h-[18px] w-[18px]" />
                  {item.label}
                </NavLink>
              ))}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <div className="flex min-h-screen flex-1 flex-col">
        <Topbar title={title} onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  )
}
