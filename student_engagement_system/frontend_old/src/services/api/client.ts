/**
 * API CLIENT — INTEGRATION CONTRACT
 * ---------------------------------------------------------------------------
 * This file is the single seam between the frontend and the future backend.
 * Every function below documents:
 *   - the REST endpoint it will call
 *   - method + payload shape
 *   - the response shape (see src/types/domain.ts)
 *
 * TODAY: each function resolves from `src/mocks/data.ts` after an artificial
 * network delay, so every screen in the app is fully interactive.
 *
 * WHEN THE BACKEND IS READY: swap the body of each function for a real
 * `fetch`/axios call to `baseURL + path`. No component code changes, because
 * components only ever import from `src/services/api/*`, never from mocks
 * directly. This is the core scalability decision described in ARCHITECTURE.md.
 */

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'https://api.cognivue.app/v1'

export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? 'wss://realtime.cognivue.app'

export function simulateNetwork<T>(data: T, ms = 350): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms))
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/**
 * Real implementation (for reference — activate when backend is live):
 *
 * async function request<T>(path: string, init?: RequestInit): Promise<T> {
 *   const token = localStorage.getItem('access_token')
 *   const res = await fetch(`${API_BASE_URL}${path}`, {
 *     ...init,
 *     headers: {
 *       'Content-Type': 'application/json',
 *       ...(token ? { Authorization: `Bearer ${token}` } : {}),
 *       ...init?.headers,
 *     },
 *   })
 *   if (!res.ok) throw new ApiError(res.status, await res.text())
 *   return res.json() as Promise<T>
 * }
 */
