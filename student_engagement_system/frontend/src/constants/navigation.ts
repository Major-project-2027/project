import {
  LayoutDashboard, CalendarClock, Users, BarChart3, ClipboardList,
  FileText, Settings, HelpCircle, ShieldCheck, GraduationCap,
  Info, LifeBuoy, Sparkles,
} from 'lucide-react'
import type { UserRole } from '@/types/domain'

export interface NavItem {
  label: string
  to: string
  icon: typeof LayoutDashboard
}

export const teacherNav: NavItem[] = [
  { label: 'Dashboard', to: '/teacher', icon: LayoutDashboard },
  { label: 'Classes', to: '/teacher/classes', icon: CalendarClock },
  { label: 'Attendance', to: '/teacher/attendance', icon: Users },
  { label: 'Analytics', to: '/teacher/analytics', icon: BarChart3 },
  { label: 'Future Engagement', to: '/teacher/future-engagement-prediction', icon: Sparkles },
  { label: 'Settings', to: '/teacher/settings', icon: Settings },
]

export const studentNav: NavItem[] = [
  { label: 'Dashboard', to: '/student', icon: LayoutDashboard },
  { label: 'Classes', to: '/student/classes', icon: CalendarClock },
  { label: 'Attendance', to: '/student/attendance', icon: ClipboardList },
  { label: 'Settings', to: '/student/settings', icon: Settings },
]

export const adminNav: NavItem[] = [
  { label: 'Overview', to: '/admin', icon: LayoutDashboard },
  { label: 'Teachers', to: '/admin/teachers', icon: GraduationCap },
  { label: 'Students', to: '/admin/students', icon: Users },
  { label: 'System Health', to: '/admin/system', icon: ShieldCheck },
  { label: 'Reports', to: '/admin/reports', icon: FileText },
]

export const supportNav: NavItem[] = [
  { label: 'Help Center', to: '/help', icon: HelpCircle },
  { label: 'Support', to: '/support', icon: LifeBuoy },
  { label: 'About', to: '/about', icon: Info },
]

export function navForRole(role: UserRole): NavItem[] {
  if (role === 'teacher') return teacherNav
  if (role === 'student') return studentNav
  return adminNav
}
