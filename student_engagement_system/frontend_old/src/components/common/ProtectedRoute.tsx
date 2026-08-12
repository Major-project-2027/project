import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAppSelector } from '@/hooks/useAppStore'
import type { UserRole } from '@/types/domain'

/**
 * Route guard. Set ENFORCE_AUTH to true once a real backend issues sessions —
 * for this mock-data preview it's left off so reviewers can browse every
 * screen without signing in first.
 */
const ENFORCE_AUTH = false

export function ProtectedRoute({ role, children }: { role: UserRole; children: ReactNode }) {
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated)
  const user = useAppSelector((s) => s.auth.user)

  if (ENFORCE_AUTH && !isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  if (isAuthenticated && user && user.role !== role) {
    return <Navigate to={`/${user.role}`} replace />
  }
  return <>{children}</>
}
