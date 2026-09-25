import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, X, ShieldAlert } from 'lucide-react'

import { VideoTile } from '@/components/classroom/VideoTile'
import { ParticipantsPanel } from '@/components/classroom/ParticipantsPanel'
import { ChatPanel } from '@/components/classroom/ChatPanel'
import { ClassroomControls, type ClassroomPanel } from '@/components/classroom/ClassroomControls'
import { StageTile } from '@/components/classroom/StreamVideo'
import { Whiteboard } from '@/components/classroom/Whiteboard'
import { CameraRequestsPanel } from '@/components/classroom/CameraRequests'
import { AIMonitoringPanel } from '@/components/monitoring/AIMonitoringPanel'
import { ConfidenceRing } from '@/components/monitoring/ConfidenceRing'
import {
  AlertToastStack,
  pushAlertToast,
} from '@/components/monitoring/AlertToast'

import {
  monitoringApi,
  classesApi,
} from '@/services/api/endpoints'
import { ApiError, getIceServers } from '@/services/api/client'
import { acquireCameraTrack, acquireLocalMedia, describeMediaError } from '@/lib/media'
import { describeSdp, describeTrack, logInboundStats, rtcLog, watchPeerStates } from '@/lib/rtcDebug'
import {
  openClassroomSocket,
  sendJson,
  WS_CLOSE_FORBIDDEN,
  WS_CLOSE_REPLACED,
  WS_CLOSE_UNAUTHENTICATED,
  type CameraOffRequest,
  type ClassChatMessage,
  type RoomParticipant,
  type WelcomeMessage,
  type WhiteboardStroke,
} from '@/lib/classroomSocket'

import { Badge } from '@/components/ui/Badge'
import type { StudentLiveState } from '@/types/domain'

// Section 5 requirement: the teacher's student list is sorted by LOWEST
// predicted future engagement first, so at-risk students surface
// immediately -- current engagement is NOT the sort key. Students with
// no valid prediction yet (null/undefined -- insufficient data, no
// person, or no model loaded) sort after every student who has one.
function comparePredictedEngagement(a: StudentLiveState, b: StudentLiveState) {
  const aPredicted = a.predictedEngagement
  const bPredicted = b.predictedEngagement

  const aHasPrediction = aPredicted !== null && aPredicted !== undefined
  const bHasPrediction = bPredicted !== null && bPredicted !== undefined

  if (!aHasPrediction && !bHasPrediction) return 0
  if (!aHasPrediction) return 1
  if (!bHasPrediction) return -1

  return aPredicted - bPredicted
}

const ALERT_LABEL: Record<string, string> = {
  looking_away: 'Looking away from screen',
  drowsiness: 'Sleeping — Wake Up!',
  phone_detected: 'Mobile phone detected',
  multiple_person: 'A second person detected',
  no_person_detected: 'No person in front of camera',
  no_face_detected: 'Face not detected — student not visible',
  face_auth_failed: 'Face authentication failed',
  voice_disturbance: 'Background voice disturbance',
  camera_off: 'Camera turned off',
  attention_drop_predicted: 'Attention drop predicted',
}
function convertAIResultToStudent(
  message: any,
  existing: any,
) {
  const data = message.data ?? {}

  const engagement = Math.max(
    0,
    Math.min(
      100,
      Number(
        data.engagement_score ??
          data.engagement ??
          existing?.currentEngagement ??
          0,
      ),
    ),
  )

  const gaze = String(
    data.gaze ?? existing?.gaze ?? 'Center',
  )

  const headPose = String(
    data.head_pose ??
      existing?.headPose ??
      'Looking Forward',
  )

  const phoneDetected = Boolean(
    data.phone_detected ??
      existing?.phoneDetected ??
      false,
  )

  const personCount = Number(
    data.person_count ??
      existing?.personCount ??
      1,
  )

  // Prefer the backend's own debounced flag (a short streak of confirmed
  // empty frames, not one bad read) when present; only fall back to a raw
  // personCount==0 check for older cached entries that predate it.
  const noPersonDetected = Boolean(
    data.no_person_detected ??
      existing?.noPersonDetected ??
      personCount === 0,
  )

  // Genuine temporal both-eyes-closed detection (see
  // ai_service.process_frame's SLEEP_THRESHOLD_SECONDS tracker) --
  // relayed as-is from the same backend result the HTTP /live-monitor
  // poll already carries; this path just mirrors it for students who
  // arrive over the WebRTC signaling channel before their first
  // /live-monitor poll resolves.
  const sleeping = Boolean(
    data.sleeping ?? existing?.sleeping ?? false,
  )

  // Backend's confirmed "face not visible" state (its engagement score is
  // already decayed for it -- nothing is recomputed here).
  const noFaceDetected = Boolean(
    data.no_face_detected ?? existing?.noFaceDetected ?? false,
  )

  // Use the backend's own already-debounced active_alert (see
  // app/routers/monitoring.py's get_active_alert(), which requires
  // several consecutive frames genuinely outside the acceptable
  // laptop-screen viewing zone before 'looking_away' fires, and never
  // fires for small/natural head or gaze movement). Recomputing this
  // client-side from a single raw gaze/head-pose reading -- the
  // previous behaviour -- bypassed that debounce entirely on this
  // WebRTC-merged path and caused alert flicker/spam.
  const activeAlert = data.active_alert ?? null

  let cognitiveState = 'focused'

  if (sleeping || engagement < 40) {
    cognitiveState = 'drowsy'
  } else if (noFaceDetected) {
    // Not visible is never "focused" (gaze/head pose are only defaults).
    cognitiveState = 'distracted'
  } else if (
    !['center', 'forward'].includes(
      gaze.toLowerCase(),
    ) ||
    !['forward', 'looking forward'].includes(
      headPose.toLowerCase(),
    )
  ) {
    cognitiveState = 'distracted'
  }

  return {
    ...(existing ?? {}),

    studentId:
      message.studentId ??
      existing?.studentId,

    studentName:
      message.studentName ??
      data.name ??
      existing?.studentName ??
      'Student',

    currentEmotion:
      data.emotion ??
      existing?.currentEmotion ??
      'neutral',

    currentEngagement: engagement,

    authenticated:
      data.name &&
      data.name !== 'Unknown'
        ? true
        : existing?.authenticated ?? false,

    cognitiveState,

    activeAlert,

    blinkCount:
      data.blink_count ??
      existing?.blinkCount ??
      0,

    headPose,

    gaze,

    phoneDetected,

    personCount,

    noPersonDetected,

    noFaceDetected,

    sleeping,

    // Future-engagement prediction -- passed through as-is from the
    // backend (never recomputed client-side): null/undefined unless
    // EngagementPredictionService actually produced a real value this
    // cycle (see that module for why it currently never does -- no
    // trained LSTM model is loaded).
    predictedEngagement:
      data.predicted_engagement ??
      existing?.predictedEngagement ??
      null,

    predictionStatus:
      data.prediction_status ??
      existing?.predictionStatus ??
      'unavailable',

    attentionDropPredicted: Boolean(
      data.attention_drop_predicted ??
        existing?.attentionDropPredicted ??
        false,
    ),

    predictionThreshold:
      data.prediction_threshold ??
      existing?.predictionThreshold ??
      undefined,

    predictionTimestamp:
      data.prediction_timestamp ??
      existing?.predictionTimestamp ??
      undefined,

    predictionLabel:
      data.prediction_label ??
      existing?.predictionLabel ??
      'unavailable',

    history: [
      ...(existing?.history ?? []).slice(-19),
      engagement,
    ],
  }
}

// A student who is connected (presence) but has no AI result yet. No
// fabricated engagement number: 0 with an empty history, excluded from the
// class average until real results arrive.
function baseStudent(p: RoomParticipant): StudentLiveState {
  return {
    studentId: p.userId,
    studentName: p.name,
    cameraOn: p.media.camera,
    micOn: p.media.mic,
    handRaised: p.media.hand,
    currentEngagement: 0,
    currentEmotion: 'neutral',
    cognitiveState: 'focused',
    authenticated: true,
    history: [],
  }
}

export function TeacherLiveClassroomPage() {
  const { classId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // -------------------------------------------------------------------------
  // Local media (real devices only -- nothing here is faked)
  // -------------------------------------------------------------------------

  const cameraTrackRef = useRef<MediaStreamTrack | null>(null)
  const micTrackRef = useRef<MediaStreamTrack | null>(null)
  const screenTrackRef = useRef<MediaStreamTrack | null>(null)

  const [cameraOn, setCameraOn] = useState(false)
  const [micOn, setMicOn] = useState(false)
  const [screenSharing, setScreenSharing] = useState(false)
  const [micAvailable, setMicAvailable] = useState(true)
  const [mediaReady, setMediaReady] = useState(false)
  const [mediaNotice, setMediaNotice] = useState<string | null>(null)
  // What the teacher currently sends as video (camera or screen), shown
  // in their own preview tile.
  const [previewStream, setPreviewStream] = useState<MediaStream | null>(null)

  const [panel, setPanel] = useState<ClassroomPanel>('monitoring')

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [dismissedAlert, setDismissedAlert] = useState(false)

  // -------------------------------------------------------------------------
  // Classroom socket / WebRTC
  // -------------------------------------------------------------------------

  const signalingRef = useRef<WebSocket | null>(null)
  // key: participant key ("student:<id>")
  const peersRef = useRef<Record<string, RTCPeerConnection>>({})
  const pendingCandidatesRef = useRef<Record<string, RTCIceCandidateInit[]>>({})

  const [socketError, setSocketError] = useState<string | null>(null)
  const [selfKey, setSelfKey] = useState<string | null>(null)
  const [participants, setParticipants] = useState<RoomParticipant[]>([])
  // key: studentId
  const [remoteStreams, setRemoteStreams] = useState<Record<string, MediaStream>>({})

  const [chat, setChat] = useState<ClassChatMessage[]>([])
  const [unreadChat, setUnreadChat] = useState(0)
  const panelRef = useRef<ClassroomPanel>(panel)
  panelRef.current = panel

  const strokesRef = useRef<WhiteboardStroke[]>([])
  const [strokeCount, setStrokeCount] = useState(0)
  const [clearToken, setClearToken] = useState(0)
  const [whiteboardOpen, setWhiteboardOpen] = useState(false)

  // Pending student camera-off requests (the server holds the truth).
  const [cameraRequests, setCameraRequests] = useState<CameraOffRequest[]>([])

  // -------------------------------------------------------------------------
  // Students received through WebRTC / AI results
  // -------------------------------------------------------------------------

  const [connectedStudents, setConnectedStudents] = useState<StudentLiveState[]>([])

  // -------------------------------------------------------------------------
  // API data
  // -------------------------------------------------------------------------

  const classQuery = useQuery({
    queryKey: ['class', classId],
    queryFn: () => classesApi.get(classId ?? ''),
    enabled: Boolean(classId),
    retry: false,
  })

  const studentsQuery = useQuery({
    queryKey: ['live-students', classId],
    queryFn: () => monitoringApi.liveStudents(classId),
    refetchInterval: 8000,
    enabled: Boolean(classId),
  })

  const apiStudents = studentsQuery.data ?? []

  // -------------------------------------------------------------------------
  // Merge presence + AI monitoring students + WebRTC-connected students
  // -------------------------------------------------------------------------

  const presentStudents = participants.filter((p) => p.role === 'student')

  const students: StudentLiveState[] = (() => {
    const merged = new Map<string, StudentLiveState>()

    // Ids are normalized to strings: /live-monitor returns numeric ids while
    // presence/signaling use strings, and a 5 vs "5" mismatch would split
    // one student into two tiles (one with the video, one without).
    for (const student of apiStudents) {
      const studentId = String(student.studentId)
      merged.set(studentId, { ...student, studentId })
    }

    // The live per-frame result (classroom socket) wins over the 8s
    // /live-monitor poll once it carries AI data -- otherwise the tile
    // showed a score up to 8s stale (e.g. still 100 after the student left
    // the camera). Before the first live result, the poll fills in.
    for (const student of connectedStudents) {
      const studentId = String(student.studentId)
      const existing = merged.get(studentId)
      const hasLiveResult = student.history.length > 0
      merged.set(
        studentId,
        existing
          ? hasLiveResult
            ? { ...existing, ...student, studentId }
            : { ...student, ...existing, studentId }
          : { ...student, studentId },
      )
    }

    // Connected students always get a tile; their real camera/mic/hand
    // state comes from presence, never assumed.
    for (const p of presentStudents) {
      const existing = merged.get(p.userId)
      merged.set(p.userId, {
        ...(existing ?? baseStudent(p)),
        cameraOn: p.media.camera,
        micOn: p.media.mic,
        handRaised: p.media.hand,
      })
    }

    // Sorted dynamically on every render (re-evaluated whenever
    // apiStudents/connectedStudents change, i.e. whenever new predictions
    // arrive), never alphabetically and never by current engagement.
    return Array.from(merged.values()).sort(comparePredictedEngagement)
  })()

  const selected =
    students.find((s) => s.studentId === selectedId) ??
    students[0]

  const withAi = students.filter((s) => s.history.length > 0)
  const avgEngagement = Math.round(
    withAi.reduce((total, student) => total + student.currentEngagement, 0) / (withAi.length || 1),
  )

  const activeAlerts = students.filter(
    (student) => student.activeAlert,
  )

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  const send = (payload: unknown) => sendJson(signalingRef.current, payload)

  const currentVideoTrack = () =>
    screenTrackRef.current ?? cameraTrackRef.current

  const refreshPreview = () => {
    const track = currentVideoTrack()
    setPreviewStream(track ? new MediaStream([track]) : null)
  }

  // Swap the outgoing video on every student connection -- no
  // renegotiation needed, the video transceiver already exists.
  const replaceOutgoing = (kind: 'video' | 'audio', track: MediaStreamTrack | null) => {
    for (const peer of Object.values(peersRef.current)) {
      for (const transceiver of peer.getTransceivers()) {
        if (transceiver.receiver.track?.kind === kind && transceiver.currentDirection !== 'stopped') {
          transceiver.sender.replaceTrack(track).catch((error) =>
            console.warn(`Unable to replace ${kind} track:`, error),
          )
        }
      }
    }
  }

  const broadcastMediaState = (state: { camera: boolean; mic: boolean; screen: boolean }) => {
    send({ type: 'media_state', ...state })
  }

  const closePeer = (key: string) => {
    peersRef.current[key]?.close()
    delete peersRef.current[key]
    delete pendingCandidatesRef.current[key]
  }

  // -------------------------------------------------------------------------
  // End class
  // -------------------------------------------------------------------------

  const endMutation = useMutation({
    mutationFn: () => classesApi.end(classId ?? ''),

    onSuccess: () => {
      // Tell every currently-connected student immediately, over the same
      // classroom socket already used for WebRTC + AI results, instead of
      // making them wait for their next analyze-frame poll to notice.
      send({ type: 'class_ended' })

      queryClient.invalidateQueries({ queryKey: ['classes'] })
      queryClient.invalidateQueries({ queryKey: ['attendance'] })

      navigate('/teacher')
    },
  })

  // -------------------------------------------------------------------------
  // Timer
  // -------------------------------------------------------------------------

  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((value) => value + 1)
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  // =========================================================================
  // MEDIA + CLASSROOM SOCKET
  // =========================================================================

  useEffect(() => {
    if (!classId) {
      return
    }

    let cancelled = false
    let ws: WebSocket | null = null

    // -----------------------------------------------------------------------
    // Student offer -> answer with the teacher's camera + microphone
    // -----------------------------------------------------------------------

    const handleOffer = async (message: any) => {
      const key: string = message.from
      const studentId = String(message.studentId)
      const studentName: string = message.studentName ?? 'Student'

      rtcLog('WEBRTC', 'teacher offer received', studentId, describeSdp(message.offer?.sdp))

      // Candidates that arrived for this student before/while the offer
      // was handled must survive the close of any previous connection.
      const queued = pendingCandidatesRef.current[key] ?? []
      closePeer(key)

      const peer = new RTCPeerConnection({ iceServers: getIceServers() })
      peersRef.current[key] = peer
      pendingCandidatesRef.current[key] = queued
      watchPeerStates(peer, `teacher<-student ${studentId}`)

      setConnectedStudents((current) =>
        current.some((s) => s.studentId === studentId)
          ? current
          : [...current, { ...baseStudent({ key, role: 'student', userId: studentId, name: studentName, media: { camera: true, mic: false, screen: false, hand: false }, connectedAt: '' }) }],
      )

      // Receive the student's camera + microphone. One stream per peer
      // connection (so it always belongs to THIS student), and a new
      // MediaStream object per added track so the tile re-attaches it.
      const remote = new MediaStream()
      peer.ontrack = (event) => {
        rtcLog('TEACHER REMOTE TRACK', studentId, {
          ...describeTrack(event.track),
          streams: event.streams.length,
        })
        if (!remote.getTracks().includes(event.track)) {
          remote.addTrack(event.track)
        }
        const stream = new MediaStream(remote.getTracks())
        setRemoteStreams((current) => ({ ...current, [studentId]: stream }))
      }

      peer.onicecandidate = (event) => {
        if (event.candidate) {
          send({ type: 'candidate', to: key, candidate: event.candidate })
        }
      }

      peer.onconnectionstatechange = () => {
        if (peer.connectionState === 'connected') {
          window.setTimeout(() => logInboundStats(peer, `teacher<-student ${studentId}`), 4000)
        }
        // On failure the student re-offers with a fresh connection.
        if (peer.connectionState === 'failed' || peer.connectionState === 'closed') {
          if (peersRef.current[key] === peer) {
            closePeer(key)
            setRemoteStreams(({ [studentId]: _gone, ...rest }) => rest)
          }
        }
      }

      await peer.setRemoteDescription(new RTCSessionDescription(message.offer))
      if (peersRef.current[key] !== peer) return // superseded by a newer offer

      // Attach the teacher's current outgoing media to the transceivers
      // the student's offer created (video + audio).
      for (const transceiver of peer.getTransceivers()) {
        const kind = transceiver.receiver.track?.kind
        if (kind === 'video') {
          await transceiver.sender.replaceTrack(currentVideoTrack())
          transceiver.direction = 'sendrecv'
        } else if (kind === 'audio') {
          await transceiver.sender.replaceTrack(micTrackRef.current)
          transceiver.direction = 'sendrecv'
        }
      }

      for (const candidate of pendingCandidatesRef.current[key] ?? []) {
        try {
          await peer.addIceCandidate(new RTCIceCandidate(candidate))
        } catch (error) {
          console.error('Failed to add queued ICE candidate:', error)
        }
      }
      pendingCandidatesRef.current[key] = []

      const answer = await peer.createAnswer()
      await peer.setLocalDescription(answer)
      if (peersRef.current[key] !== peer) return

      rtcLog('WEBRTC', 'teacher answer created', studentId, describeSdp(answer.sdp))
      send({ type: 'answer', to: key, answer })
    }

    const handleCandidate = async (message: any) => {
      const key: string = message.from
      const peer = peersRef.current[key]

      if (!peer || !peer.remoteDescription) {
        pendingCandidatesRef.current[key] = [
          ...(pendingCandidatesRef.current[key] ?? []),
          message.candidate,
        ]
        return
      }

      try {
        await peer.addIceCandidate(new RTCIceCandidate(message.candidate))
      } catch (error) {
        console.error('Failed to add ICE candidate:', error)
      }
    }

    const handleAiResult = (message: any) => {
      const studentId = String(message.studentId)
      message = { ...message, studentId }

      // Temporary latency diagnostics: student frame capture -> shown here.
      // (Accurate when both run on the same machine; otherwise includes
      // the two clocks' offset.)
      const capturedAt = Number(message.data?.client_timing?.captured_at)
      if (capturedAt) {
        console.info('[AI TIMING] teacher display', {
          studentId,
          alert: message.data?.active_alert ?? null,
          capture_to_teacher_ms: Date.now() - capturedAt,
        })
      }

      setConnectedStudents((current) => {
        const existing = current.find((student) => student.studentId === studentId)
        const updatedStudent = convertAIResultToStudent(message, existing) as StudentLiveState

        // Engagement history used for attendance/history is persisted
        // server-side (engagement_records, keyed by session_id +
        // student_id) by the /ai/analyze-frame endpoint itself.
        if (existing) {
          return current.map((student) =>
            student.studentId === studentId ? { ...student, ...updatedStudent } : student,
          )
        }

        return [
          ...current,
          {
            ...updatedStudent,
            studentId,
            studentName: message.studentName ?? 'Student',
            cameraOn: true,
            micOn: false,
            handRaised: false,
            currentEngagement: updatedStudent.currentEngagement ?? 0,
            currentEmotion: updatedStudent.currentEmotion ?? 'neutral',
            cognitiveState: updatedStudent.cognitiveState ?? 'focused',
            authenticated: updatedStudent.authenticated ?? false,
            history: updatedStudent.history ?? [updatedStudent.currentEngagement ?? 0],
          },
        ]
      })
    }

    const start = async () => {
      // 1. Camera + microphone (before connecting, so the first answer to
      //    every student already carries them).
      const media = await acquireLocalMedia({ video: true, audio: true })

      if (cancelled) {
        media.stream.getTracks().forEach((t) => t.stop())
        return
      }

      cameraTrackRef.current = media.videoTrack
      micTrackRef.current = media.audioTrack
      setCameraOn(Boolean(media.videoTrack))
      setMicOn(Boolean(media.audioTrack))
      setMicAvailable(Boolean(media.audioTrack))
      setMediaNotice([media.cameraError, media.micError].filter(Boolean).join(' ') || null)
      setPreviewStream(media.videoTrack ? new MediaStream([media.videoTrack]) : null)
      setMediaReady(true)

      // 2. Authenticated classroom socket.
      ws = openClassroomSocket(classId)
      signalingRef.current = ws

      ws.onmessage = async (event) => {
        let message: any
        try {
          message = JSON.parse(event.data)
        } catch {
          return
        }

        try {
          switch (message.type) {
            case 'welcome': {
              const welcome = message as WelcomeMessage
              setSelfKey(welcome.self.key)
              setParticipants([welcome.self, ...welcome.participants])
              strokesRef.current = [...welcome.whiteboard.strokes]
              setStrokeCount(strokesRef.current.length)
              setClearToken((t) => t + 1)
              setWhiteboardOpen(welcome.whiteboard.open)
              setChat(welcome.chat)
              setCameraRequests(welcome.cameraRequests ?? [])
              send({
                type: 'media_state',
                camera: Boolean(cameraTrackRef.current),
                mic: Boolean(micTrackRef.current?.enabled),
                screen: false,
              })
              break
            }
            case 'participant_joined':
              setParticipants((current) => [
                ...current.filter((p) => p.key !== message.participant.key),
                message.participant,
              ])
              break
            case 'participant_updated':
              setParticipants((current) =>
                current.map((p) => (p.key === message.participant.key ? message.participant : p)),
              )
              break
            case 'participant_left': {
              const key: string = message.key
              setParticipants((current) => current.filter((p) => p.key !== key))
              if (key.startsWith('student:')) {
                const studentId = key.slice('student:'.length)
                closePeer(key)
                setRemoteStreams(({ [studentId]: _gone, ...rest }) => rest)
                setConnectedStudents((current) => current.filter((s) => s.studentId !== studentId))
              }
              break
            }
            case 'offer':
              await handleOffer(message)
              break
            case 'candidate':
              await handleCandidate(message)
              break
            case 'ai_result':
              handleAiResult(message)
              break
            case 'AI_ALERT':
              // A student's AI detection (built and rate-limited by the
              // server). Shown for any student, selected or not.
              pushAlertToast({
                studentName: message.studentName ?? 'Student',
                message: message.message ?? ALERT_LABEL[message.alertType] ?? 'Attention issue detected',
                severity: message.severity === 'critical' ? 'critical' : 'warning',
                // Once per confirmed sleeping episode (the student only
                // signals transitions into an alert).
                sound: message.alertType === 'drowsiness',
              })
              break
            case 'camera_request': {
              const request = message.request as CameraOffRequest
              setCameraRequests((current) => [...current.filter((r) => r.id !== request.id), request])
              pushAlertToast({
                studentName: request.studentName,
                message: `Camera-off request: ${request.reason}`,
                severity: 'warning',
              })
              break
            }
            case 'camera_request_removed':
              setCameraRequests((current) => current.filter((r) => r.id !== message.id))
              break
            case 'camera_off_blocked':
              pushAlertToast({
                studentName: message.studentName ?? 'Student',
                message: 'Tried to turn the camera off without approval',
                severity: 'warning',
              })
              break
            case 'chat':
              setChat((current) => [...current, message as ClassChatMessage])
              if (panelRef.current !== 'chat') {
                setUnreadChat((n) => n + 1)
              }
              break
            case 'error':
              if (message.code === 401 || message.code === 403 || message.code === 409) {
                setSocketError(message.message ?? 'You are not authorized to open this class.')
              } else {
                console.warn('Classroom socket error:', message.message)
              }
              break
          }
        } catch (error) {
          console.error('Teacher classroom message error:', error)
        }
      }

      ws.onclose = (event) => {
        if (event.code === WS_CLOSE_FORBIDDEN || event.code === WS_CLOSE_UNAUTHENTICATED || event.code === WS_CLOSE_REPLACED) {
          setSocketError((current) => current ?? 'The classroom connection was closed.')
        }
      }
    }

    start().catch((error) => {
      console.error('Unable to start the live classroom:', error)
      setMediaNotice('Unable to start the live classroom. Please reload the page.')
    })

    return () => {
      cancelled = true
      ws?.close()
      signalingRef.current = null

      Object.keys(peersRef.current).forEach(closePeer)
      peersRef.current = {}
      pendingCandidatesRef.current = {}

      cameraTrackRef.current?.stop()
      micTrackRef.current?.stop()
      screenTrackRef.current?.stop()
      cameraTrackRef.current = null
      micTrackRef.current = null
      screenTrackRef.current = null

      setConnectedStudents([])
      setRemoteStreams({})
      setParticipants([])
      setCameraRequests([])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId])

  // =========================================================================
  // CONTROLS
  // =========================================================================

  const toggleMic = async () => {
    const track = micTrackRef.current

    if (track) {
      track.enabled = !track.enabled
      setMicOn(track.enabled)
      broadcastMediaState({ camera: Boolean(cameraTrackRef.current), mic: track.enabled, screen: screenSharing })
      return
    }

    // No microphone yet (denied/unavailable at start) -- try again.
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const newTrack = stream.getAudioTracks()[0]
      micTrackRef.current = newTrack
      replaceOutgoing('audio', newTrack)
      setMicOn(true)
      setMicAvailable(true)
      setMediaNotice(null)
      broadcastMediaState({ camera: Boolean(cameraTrackRef.current), mic: true, screen: screenSharing })
    } catch (error) {
      setMediaNotice(describeMediaError(error, 'microphone'))
    }
  }

  const toggleCamera = async () => {
    if (cameraTrackRef.current) {
      // Really stop the camera (the light goes off), and tell students to
      // show the placeholder rather than a frozen frame.
      cameraTrackRef.current.stop()
      cameraTrackRef.current = null
      if (!screenTrackRef.current) {
        replaceOutgoing('video', null)
      }
      setCameraOn(false)
      refreshPreview()
      broadcastMediaState({ camera: false, mic: Boolean(micTrackRef.current?.enabled), screen: screenSharing })
      return
    }

    try {
      const track = await acquireCameraTrack()
      cameraTrackRef.current = track
      if (!screenTrackRef.current) {
        replaceOutgoing('video', track)
      }
      setCameraOn(true)
      setMediaNotice(null)
      refreshPreview()
      broadcastMediaState({ camera: true, mic: Boolean(micTrackRef.current?.enabled), screen: screenSharing })
    } catch (error) {
      setMediaNotice(describeMediaError(error, 'camera'))
    }
  }

  const stopScreenShare = () => {
    const track = screenTrackRef.current
    if (!track) return
    screenTrackRef.current = null
    track.stop()
    // Back to the camera (or nothing, if the camera is off).
    replaceOutgoing('video', cameraTrackRef.current)
    setScreenSharing(false)
    refreshPreview()
    broadcastMediaState({ camera: Boolean(cameraTrackRef.current), mic: Boolean(micTrackRef.current?.enabled), screen: false })
  }

  const toggleScreenShare = async () => {
    if (screenTrackRef.current) {
      stopScreenShare()
      return
    }

    try {
      const display = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false })
      const track = display.getVideoTracks()[0]
      screenTrackRef.current = track
      // The browser's own "Stop sharing" button ends the track.
      track.addEventListener('ended', stopScreenShare)
      replaceOutgoing('video', track)
      setScreenSharing(true)
      setMediaNotice(null)
      refreshPreview()
      broadcastMediaState({ camera: Boolean(cameraTrackRef.current), mic: Boolean(micTrackRef.current?.enabled), screen: true })
    } catch (error) {
      setMediaNotice(describeMediaError(error, 'screen'))
    }
  }

  const toggleWhiteboard = () => {
    const next = !whiteboardOpen
    setWhiteboardOpen(next)
    send({ type: next ? 'wb_open' : 'wb_close' })
  }

  const onStroke = (stroke: WhiteboardStroke) => {
    strokesRef.current.push(stroke)
    setStrokeCount(strokesRef.current.length)
    send({ type: 'wb_stroke', stroke })
  }

  const clearBoard = () => {
    strokesRef.current.length = 0
    setStrokeCount(0)
    setClearToken((t) => t + 1)
    send({ type: 'wb_clear' })
  }

  const togglePanel = (next: Exclude<ClassroomPanel, 'none'>) => {
    setPanel((value) => (value === next ? 'none' : next))
    if (next === 'chat') {
      setUnreadChat(0)
    }
  }

  const timer = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  // =========================================================================
  // UI
  // =========================================================================

  if (socketError || (classQuery.error && (classQuery.error as ApiError).status === 403)) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#080b12] p-6">
        <div className="max-w-md rounded-2xl bg-[#171923] p-6 text-center shadow-2xl">
          <ShieldAlert className="mx-auto h-8 w-8 text-critical-400" />
          <p className="mt-3 text-lg font-semibold text-white">Can't open this class</p>
          <p className="mt-1 text-sm text-white/60">
            {socketError ?? (classQuery.error as Error).message}
          </p>
          <button
            onClick={() => navigate('/teacher')}
            className="mt-4 rounded-lg bg-focus-500 px-4 py-2 text-sm font-medium text-white hover:bg-focus-600"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    )
  }

  const selfName = sessionStorage.getItem('user_name') ?? 'You'

  const selfTile = (
    <div className="relative aspect-video overflow-hidden rounded-xl bg-[#161b28]">
      <StageTile
        name={selfName}
        label={screenSharing ? 'You (sharing screen)' : 'You (teacher)'}
        stream={previewStream}
        videoOn={Boolean(previewStream)}
        micOn={micOn}
        screenSharing={screenSharing}
        muted
        mirrored
        testId="teacher-self-video"
      />
    </div>
  )

  const studentTiles = students.map((student) => (
    <VideoTile
      key={student.studentId}
      student={student}
      stream={remoteStreams[student.studentId] ?? null}
      selected={student.studentId === selected?.studentId}
      onSelect={() => {
        setSelectedId(student.studentId)
        setPanel('monitoring')
      }}
    />
  ))

  return (
    <div className="flex h-screen flex-col bg-[#080b12]">
      <AlertToastStack />

      {/* Header */}

      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-xs font-medium text-critical-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-critical-500" />
            LIVE
          </span>

          <p className="text-sm font-semibold text-white">
            {classQuery.data?.title ?? 'Live class'}
          </p>

          <Badge variant="neutral" className="bg-white/10 text-white" data-testid="connected-count">
            {presentStudents.length} connected
          </Badge>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 sm:flex">
            <ConfidenceRing value={avgEngagement} size={36} strokeWidth={4} />
            <span className="text-xs text-white/60">class avg.</span>
          </div>
        </div>
      </div>

      {/* Device notice (permission denied / unavailable / in use) */}

      {mediaNotice && (
        <div className="flex items-center justify-between gap-3 bg-attention-500/15 px-4 py-2 text-sm text-attention-200" role="status">
          <span className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {mediaNotice}
          </span>
          <button onClick={() => setMediaNotice(null)} aria-label="Dismiss">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Alert banner */}

      {activeAlerts.length > 0 && !dismissedAlert && (
        <div className="flex items-center justify-between gap-3 bg-critical-500/15 px-4 py-2 text-sm text-critical-300">
          <span className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            {activeAlerts.length} student(s) currently need attention — {activeAlerts[0].studentName} (
            {ALERT_LABEL[activeAlerts[0].activeAlert ?? ''] ?? 'flagged'})
          </span>

          <button onClick={() => setDismissedAlert(true)} aria-label="Dismiss">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Main content */}

      <div className="flex flex-1 overflow-hidden">
        <div className="flex min-w-0 flex-1 flex-col gap-3 overflow-y-auto p-3">
          {whiteboardOpen ? (
            <>
              <div className="min-h-[320px] flex-1">
                <Whiteboard
                  strokes={strokesRef.current}
                  strokeCount={strokeCount}
                  clearToken={clearToken}
                  editable
                  onStroke={onStroke}
                  onClear={clearBoard}
                  onClose={toggleWhiteboard}
                />
              </div>
              <div className="grid shrink-0 grid-cols-3 gap-2.5 sm:grid-cols-4 lg:grid-cols-6">
                {selfTile}
                {studentTiles}
              </div>
            </>
          ) : (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {selfTile}
              {studentTiles}
              {students.length === 0 && (
                <div className="col-span-full flex items-center justify-center rounded-xl border border-dashed border-white/10 p-8 text-center text-white/50">
                  <div>
                    <p className="text-sm">Waiting for students to join…</p>
                    <p className="mt-1 text-xs">
                      {mediaReady ? 'Only students you allowed for this class can join.' : 'Starting your camera and microphone…'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Side panel */}

        {panel !== 'none' && (
          <div className="w-[320px] shrink-0 border-l border-white/10 bg-[#0f131e]">
            {panel === 'participants' && (
              <ParticipantsPanel participants={participants} selfKey={selfKey} students={students} />
            )}

            {panel === 'chat' && (
              <ChatPanel
                messages={chat}
                selfKey={selfKey}
                disabled={!selfKey}
                onSend={(text) => send({ type: 'chat', text })}
              />
            )}

            {panel === 'camera-requests' && (
              <CameraRequestsPanel
                requests={cameraRequests}
                onDecide={(id, approve) => send({ type: 'camera_request_decision', id, approve })}
              />
            )}

            {panel === 'monitoring' && selected && (
              <div className="dark h-full">
                <AIMonitoringPanel student={selected} />
              </div>
            )}

            {panel === 'monitoring' && !selected && (
              <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-white/60">
                <ShieldAlert className="h-6 w-6" />
                <p className="text-sm">Select a student tile to view their AI monitoring detail.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Controls */}

      <ClassroomControls
        role="teacher"
        micOn={micOn}
        cameraOn={cameraOn}
        micAvailable={micAvailable || !micTrackRef.current}
        screenSharing={screenSharing}
        whiteboardOpen={whiteboardOpen}
        recording
        panel={panel}
        unreadChat={unreadChat}
        cameraRequestCount={cameraRequests.length}
        onToggleMic={toggleMic}
        onToggleCamera={toggleCamera}
        onToggleScreenShare={toggleScreenShare}
        onToggleWhiteboard={toggleWhiteboard}
        onTogglePanel={togglePanel}
        onLeave={() => endMutation.mutate()}
        leaveLabel="End class"
        timer={timer}
      />
    </div>
  )
}
