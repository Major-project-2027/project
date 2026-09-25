import { WS_API_BASE_URL } from '@/services/api/client'

// Shared types + connection helper for the authenticated classroom
// WebSocket (FastAPI /ws/classes/:classId/signaling). The server derives
// identity from the token and scopes every event to this class; see
// backend/app/routers/monitoring.py.

export interface ParticipantMedia {
  camera: boolean
  mic: boolean
  screen: boolean
  hand: boolean
}

export interface RoomParticipant {
  key: string // "teacher:<id>" | "student:<id>"
  role: 'teacher' | 'student'
  userId: string
  name: string
  media: ParticipantMedia
  connectedAt: string
}

export interface ClassChatMessage {
  id: string
  senderKey: string
  senderName: string
  senderRole: 'teacher' | 'student'
  text: string
  ts: string
}

export interface WhiteboardStroke {
  id: string
  points: [number, number][] // normalized 0..1
  width: number // relative to a 1000px-wide board
  color: string
  mode: 'pen' | 'erase'
}

/** A student's pending request to turn their camera off (teacher decides). */
export interface CameraOffRequest {
  id: string
  studentKey: string
  studentId: string
  studentName: string
  reason: string
  note: string
  ts: string
}

export const CAMERA_OFF_REASONS = [
  'Technical issue',
  'Privacy issue',
  'Camera problem',
  'Network issue',
  'Other',
] as const

/** Server -> student status of their camera-off request. */
export type CameraRequestStatus = 'pending' | 'approved' | 'rejected' | 'cancelled' | 'not_approved' | 'invalid'

export interface WelcomeMessage {
  type: 'welcome'
  self: RoomParticipant
  participants: RoomParticipant[]
  whiteboard: { open: boolean; strokes: WhiteboardStroke[] }
  chat: ClassChatMessage[]
  // Teacher only: pending camera-off requests in this class.
  cameraRequests?: CameraOffRequest[]
  // Student only: an approval they already hold / a request still pending.
  cameraOffApproved?: boolean
  cameraRequestPending?: boolean
}

/** Close codes the server uses for authorization failures. */
export const WS_CLOSE_UNAUTHENTICATED = 4401
export const WS_CLOSE_FORBIDDEN = 4403
export const WS_CLOSE_REPLACED = 4409

export function openClassroomSocket(classId: string): WebSocket {
  const token = sessionStorage.getItem('access_token') ?? ''
  const ws = new WebSocket(
    `${WS_API_BASE_URL}/ws/classes/${encodeURIComponent(classId)}/signaling?token=${encodeURIComponent(token)}`,
  )

  // Keep the socket alive through idle proxies (Render closes silent
  // connections); the server answers with "pong".
  const keepAlive = window.setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 25000)
  ws.addEventListener('close', () => window.clearInterval(keepAlive))

  return ws
}

export function sendJson(ws: WebSocket | null, payload: unknown) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload))
  }
}
