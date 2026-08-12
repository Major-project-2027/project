import { NavLink } from 'react-router-dom'
import { ChevronsLeft, GraduationCap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { navForRole, supportNav } from '@/constants/navigation'
import { useAppSelector, useAppDispatch } from '@/hooks/useAppStore'
import { toggleSidebar } from '@/store/slices/uiSlice'
import type { UserRole } from '@/types/domain'
import { FocusPulse } from '@/components/monitoring/ConfidenceRing'

export function Sidebar({ role }: { role: UserRole }) {
  const collapsed = useAppSelector((s) => s.ui.sidebarCollapsed)
  const dispatch = useAppDispatch()
  const items = navForRole(role)

  return (
    <aside
      className={cn(
        'sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border-light bg-surface-light transition-all duration-200 dark:border-border-dark dark:bg-surface-dark md:flex',
        collapsed ? 'w-[76px]' : 'w-64',
      )}
    >
      <div className="flex h-16 items-center gap-2 px-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-focus-500 text-white">
          <GraduationCap className="h-5 w-5" />
        </div>
        {!collapsed && (
          <div className="flex flex-col leading-tight">
            <span className="font-display text-sm font-bold text-text-light dark:text-text-dark">Cognivue</span>
            <span className="text-[11px] text-textmuted-light dark:text-textmuted-dark">AI Classroom Suite</span>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to.split('/').length <= 2}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-focus-500/10 text-focus-600 dark:text-focus-400'
                  : 'text-textmuted-light hover:bg-black/5 hover:text-text-light dark:text-textmuted-dark dark:hover:bg-white/5 dark:hover:text-text-dark',
              )
            }
          >
            <item.icon className="h-[18px] w-[18px] shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}

        <div className="my-3 border-t border-border-light dark:border-border-dark" />

        {supportNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-focus-500/10 text-focus-600 dark:text-focus-400'
                  : 'text-textmuted-light hover:bg-black/5 hover:text-text-light dark:text-textmuted-dark dark:hover:bg-white/5 dark:hover:text-text-dark',
              )
            }
          >
            <item.icon className="h-[18px] w-[18px] shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="flex items-center justify-between border-t border-border-light p-3 dark:border-border-dark">
        {!collapsed && <FocusPulse className="opacity-70" />}
        <button
          onClick={() => dispatch(toggleSidebar())}
          className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-textmuted-light hover:bg-black/5 dark:text-textmuted-dark dark:hover:bg-white/10"
          aria-label="Toggle sidebar"
        >
          <ChevronsLeft className={cn('h-4 w-4 transition-transform', collapsed && 'rotate-180')} />
        </button>
      </div>
    </aside>
  )
}
