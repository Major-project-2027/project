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

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

// Was hardcoded to localhost with no env var at all -- fixed for
// production (Vercel frontend -> Render Flask backend) the same way
// API_BASE_URL already was. Every Flask call in endpoints.ts goes
// through this one constant, so setting VITE_FLASK_API_BASE_URL in
// Vercel's project settings is enough to repoint all of them.
export const FLASK_API_BASE_URL =
  import.meta.env.VITE_FLASK_API_BASE_URL ?? 'http://127.0.0.1:5000'

export const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL ?? 'ws://127.0.0.1:5000'

// The WebRTC signaling WebSocket (/ws/classes/:id/signaling) is served
// by the SAME FastAPI app as API_BASE_URL, not a separate service --
// derived from it (http->ws, https->wss) rather than a second env var,
// so it can never drift out of sync with wherever FastAPI actually is.
export const WS_API_BASE_URL = API_BASE_URL.replace(/^http/, 'ws')

// WebRTC ICE servers for the teacher<->student peer connections. STUN
// (Google's public server) is always included -- unchanged from before,
// works fine when both peers are reachable without traversing a
// restrictive NAT/firewall (e.g. same LAN, which is all local testing
// has exercised). A TURN server is OPTIONAL and only added when all
// three VITE_TURN_* vars are set; with none set, this returns exactly
// the same STUN-only config as today -- no behavior change until a TURN
// provider is actually configured. TURN matters once real users are on
// different real-world networks: pure STUN frequently cannot establish
// a connection through symmetric NAT/CGNAT/some corporate firewalls, and
// there is no way to fix that from application code alone -- it requires
// a running TURN relay (e.g. Twilio Network Traversal, Metered.ca, or a
// self-hosted coturn instance).
export function getIceServers(): RTCIceServer[] {
  const servers: RTCIceServer[] = [{ urls: 'stun:stun.l.google.com:19302' }]

  const turnUrl = import.meta.env.VITE_TURN_URL
  const turnUsername = import.meta.env.VITE_TURN_USERNAME
  const turnCredential = import.meta.env.VITE_TURN_CREDENTIAL

  if (turnUrl && turnUsername && turnCredential) {
    servers.push({
      urls: turnUrl,
      username: turnUsername,
      credential: turnCredential,
    })
  }

  return servers
}

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
