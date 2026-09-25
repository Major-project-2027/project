import { useRef } from 'react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import {
  AlertTriangle,
  Phone,
  Users,
  UserX,
  EyeOff,
  X,
  ShieldAlert,
  Loader2,
} from 'lucide-react'

import { ParticipantsPanel } from '@/components/classroom/ParticipantsPanel'
import { ChatPanel } from '@/components/classroom/ChatPanel'
import { ClassroomControls, type ClassroomPanel } from '@/components/classroom/ClassroomControls'
import { StageTile } from '@/components/classroom/StreamVideo'
import { Whiteboard } from '@/components/classroom/Whiteboard'
import { CameraOffRequestModal } from '@/components/classroom/CameraRequests'
import { ConfidenceRing } from '@/components/monitoring/ConfidenceRing'
import { Badge } from '@/components/ui/Badge'

import { currentStudent } from '@/mocks/data'
import { classesApi } from '@/services/api/endpoints'
import { API_BASE_URL, FLASK_API_BASE_URL, getIceServers } from '@/services/api/client'
import { acquireCameraTrack, acquireLocalMedia, describeMediaError } from '@/lib/media'
import { describeSdp, describeTrack, logInboundStats, rtcLog, watchPeerStates } from '@/lib/rtcDebug'
import {
  openClassroomSocket,
  sendJson,
  WS_CLOSE_FORBIDDEN,
  WS_CLOSE_REPLACED,
  WS_CLOSE_UNAUTHENTICATED,
  type CameraRequestStatus,
  type ClassChatMessage,
  type RoomParticipant,
  type WelcomeMessage,
  type WhiteboardStroke,
} from '@/lib/classroomSocket'

type Access = 'checking' | 'allowed' | 'denied'

export function StudentLiveClassroomPage() {
  const navigate = useNavigate()
  const { classId } = useParams()

  // Real identity of the logged-in student -- must match what /ai/analyze-frame
  // is sent so the teacher's WebRTC tile and AI-monitoring tile merge into one
  // student instead of appearing as two separate (mock vs. real) entries.
  // sessionStorage (not localStorage) is deliberate: localStorage is shared
  // across every tab on this origin, so a teacher and a student logged in
  // in two tabs of the same browser would otherwise silently overwrite each
  // other's identity here, tagging AI results with the wrong user_id.
  // (The server re-derives identity from the token regardless.)
  const realStudentId = sessionStorage.getItem('user_id') ?? currentStudent.id
  const realStudentName = sessionStorage.getItem('user_name') ?? currentStudent.name

  // ---------------------------------------------------------------------------
  // ACCESS CHECK -- nothing (camera, socket, AI) starts until the server
  // confirms this student is allowed in this class. The server enforces it
  // again on the socket and on every AI frame; this just avoids starting
  // media for someone who will be refused.
  // ---------------------------------------------------------------------------

  const [access, setAccess] = useState<Access>('checking')
  const [accessMessage, setAccessMessage] = useState<string | null>(null)
  const accessRef = useRef<Access>('checking')
  accessRef.current = access

  useEffect(() => {
    let cancelled = false

    const checkAccess = async () => {
      const token = sessionStorage.getItem('access_token')

      if (!token || !classId) {
        setAccessMessage('Please log in again.')
        setAccess('denied')
        return
      }

      try {
        const response = await fetch(`${FLASK_API_BASE_URL}/join-class`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ class_code: classId }),
        })

        const result = await response.json()

        if (cancelled) return

        if (response.ok && result.success) {
          setAccess('allowed')
        } else {
          setAccessMessage(result.error || 'You are not authorized to join this class.')
          setAccess('denied')
        }
      } catch {
        if (!cancelled) {
          setAccessMessage('Unable to reach the server. Please check your connection and try again.')
          setAccess('denied')
        }
      }
    }

    checkAccess()

    return () => {
      cancelled = true
    }
  }, [classId])

  const classQuery = useQuery({
    queryKey: ['class', classId],
    queryFn: () => classesApi.get(classId ?? ''),
    enabled: access === 'allowed',
    retry: false,
  })

  // ---------------------------------------------------------------------------
  // Local media / classroom state
  // ---------------------------------------------------------------------------

  const [micOn, setMicOn] = useState(false)
  const [cameraOn, setCameraOn] = useState(false)
  const [handRaised, setHandRaised] = useState(false)
  const [micAvailable, setMicAvailable] = useState(true)
  const [mediaNotice, setMediaNotice] = useState<string | null>(null)
  const [panel, setPanel] = useState<ClassroomPanel>('none')
  const [seconds, setSeconds] = useState(0)
  const [myEngagement, setMyEngagement] = useState(74)

  const [aiAlert, setAiAlert] = useState<string | null>(null)
  const [showAiAlert, setShowAiAlert] = useState(false)
  const [classEnded, setClassEnded] = useState(false)
  // Interval/WS callbacks below are set up once (empty dependency arrays)
  // and would otherwise only ever see the `classEnded` value from that
  // first render via closure capture. The ref gives them a live read.
  const classEndedRef = useRef(false)
  const markClassEnded = () => {
    classEndedRef.current = true
    setClassEnded(true)
  }

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const aiCanvasRef = useRef<HTMLCanvasElement | null>(null)
  // True while an /ai/analyze-frame request is still running -- see the
  // AI analysis interval below.
  const aiRequestInFlightRef = useRef(false)
  // Set when the AI endpoint refuses this student (401/403): stop sending.
  const aiStoppedRef = useRef(false)

  const localStreamRef = useRef<MediaStream>(new MediaStream())
  const cameraTrackRef = useRef<MediaStreamTrack | null>(null)
  const micTrackRef = useRef<MediaStreamTrack | null>(null)

  const peerRef = useRef<RTCPeerConnection | null>(null)
  const videoSenderRef = useRef<RTCRtpSender | null>(null)
  const audioSenderRef = useRef<RTCRtpSender | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const [selfKey, setSelfKey] = useState<string | null>(null)
  const [participants, setParticipants] = useState<RoomParticipant[]>([])
  const [teacherStream, setTeacherStream] = useState<MediaStream | null>(null)

  const [chat, setChat] = useState<ClassChatMessage[]>([])
  const [unreadChat, setUnreadChat] = useState(0)
  const panelRef = useRef<ClassroomPanel>(panel)
  panelRef.current = panel

  const strokesRef = useRef<WhiteboardStroke[]>([])
  const [strokeCount, setStrokeCount] = useState(0)
  const [clearToken, setClearToken] = useState(0)
  const [whiteboardOpen, setWhiteboardOpen] = useState(false)

  // Camera-off approval: the camera stays on until the teacher approves.
  const [cameraRequest, setCameraRequest] = useState<'idle' | 'pending' | 'approved' | 'rejected'>('idle')
  const [showCameraRequestModal, setShowCameraRequestModal] = useState(false)
  const cameraOffApprovedRef = useRef(false)

  // "Approved" / "rejected" are shown briefly, then the banner clears.
  useEffect(() => {
    if (cameraRequest !== 'approved' && cameraRequest !== 'rejected') return
    const timeout = window.setTimeout(() => setCameraRequest('idle'), 6000)
    return () => window.clearTimeout(timeout)
  }, [cameraRequest])

  const teacher = participants.find((p) => p.role === 'teacher') ?? null

  const send = (payload: unknown) => sendJson(wsRef.current, payload)

  // Read through a ref: socket handlers are created once at mount and
  // would otherwise report that render's (stale) hand state.
  const handRaisedRef = useRef(handRaised)
  handRaisedRef.current = handRaised

  const mediaState = (overrides: Partial<{ camera: boolean; mic: boolean; hand: boolean }> = {}) => ({
    type: 'media_state',
    camera: Boolean(cameraTrackRef.current),
    mic: Boolean(micTrackRef.current?.enabled),
    hand: handRaisedRef.current,
    ...overrides,
  })

  // ---------------------------------------------------------------------------
  // DROWSINESS ALERT SOUND
  // A drowsy/sleeping student may have their eyes closed, so a silent
  // toast alone may go unnoticed -- play a short, distinct ~2s tone the
  // moment `active_alert` TRANSITIONS into 'drowsiness'. previousAlertRef
  // (not the `aiAlert` React state) drives the transition check so this
  // never re-fires every poll while still drowsy, only re-arms once the
  // alert has cleared. soundPlayingRef blocks overlapping instances.
  // ---------------------------------------------------------------------------

  const previousAlertRef = useRef<string | null>(null)
  // Last alert logged as shown (latency diagnostics only).
  const lastShownAlertRef = useRef<string | null>(null)
  const soundPlayingRef = useRef(false)
  const audioCtxRef = useRef<AudioContext | null>(null)

  function getAudioContext(): AudioContext | null {
    if (!audioCtxRef.current) {
      const Ctx = window.AudioContext || (window as any).webkitAudioContext
      if (Ctx) {
        audioCtxRef.current = new Ctx()
      }
    }
    return audioCtxRef.current
  }

  // Browsers block audio until a user gesture unlocks the AudioContext.
  // The student has already interacted with this page (join/camera/mic
  // controls), but that gesture may land before the AudioContext exists --
  // so create/resume it on the first pointer or key interaction here too.
  useEffect(() => {
    const unlock = () => {
      const ctx = getAudioContext()
      if (ctx && ctx.state === 'suspended') {
        ctx.resume().catch(() => {})
      }
    }

    window.addEventListener('pointerdown', unlock, { once: true })
    window.addEventListener('keydown', unlock, { once: true })

    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
  }, [])

  function playDrowsinessAlertSound() {
    // Never stack overlapping instances -- one ~2s tone per confirmed
    // episode is enough, and a fresh timer already re-arms it after.
    if (soundPlayingRef.current) {
      return
    }

    const ctx = getAudioContext()

    if (!ctx) {
      return
    }

    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {})
    }

    soundPlayingRef.current = true

    try {
      const now = ctx.currentTime
      // Three short, gentle pulses spanning ~2 seconds -- noticeable
      // without being harsh/loud, and clearly finite (not a drone).
      const pulseOffsets = [0, 0.65, 1.3]

      pulseOffsets.forEach((offset) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()

        osc.type = 'sine'
        osc.frequency.value = 660

        gain.gain.setValueAtTime(0.0001, now + offset)
        gain.gain.exponentialRampToValueAtTime(0.22, now + offset + 0.05)
        gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.35)

        osc.connect(gain)
        gain.connect(ctx.destination)

        osc.start(now + offset)
        osc.stop(now + offset + 0.36)
      })
    } catch {
      // Audio is a non-essential enhancement -- never let it break alerting.
    }

    setTimeout(() => {
      soundPlayingRef.current = false
    }, 2000)
  }

  // ---------------------------------------------------------------------------
  // CAMERA + MICROPHONE + CLASSROOM SOCKET + WEBRTC
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (access !== 'allowed' || !classId) {
      return
    }

    let cancelled = false
    let ws: WebSocket | null = null
    let pendingCandidates: RTCIceCandidateInit[] = []

    const closePeer = () => {
      peerRef.current?.close()
      peerRef.current = null
      videoSenderRef.current = null
      audioSenderRef.current = null
      pendingCandidates = []
      setTeacherStream(null)
    }

    // The student starts the WebRTC connection to the teacher: send own
    // camera/mic, and receive the teacher's camera/screen + microphone on
    // the same two transceivers (both sendrecv, so a device turned on later
    // is just a replaceTrack -- no renegotiation).
    // Consecutive failed connection attempts; reset once connected.
    let failedAttempts = 0

    const offerToTeacher = async () => {
      closePeer()

      const peer = new RTCPeerConnection({ iceServers: getIceServers() })
      peerRef.current = peer
      watchPeerStates(peer, 'student->teacher')

      // Tracks are attached BEFORE createOffer, so the offer negotiates
      // m=video + m=audio. Both are sendrecv even with a device off, so
      // turning it on later is a replaceTrack, not a renegotiation.
      const local = localStreamRef.current
      rtcLog('STUDENT MEDIA', {
        videoTracks: local.getVideoTracks().length,
        video: describeTrack(cameraTrackRef.current),
        audio: describeTrack(micTrackRef.current),
      })
      videoSenderRef.current = peer.addTransceiver(cameraTrackRef.current ?? 'video', {
        direction: 'sendrecv',
        streams: [local],
      }).sender
      audioSenderRef.current = peer.addTransceiver(micTrackRef.current ?? 'audio', {
        direction: 'sendrecv',
        streams: [local],
      }).sender

      const remote = new MediaStream()
      peer.ontrack = (event) => {
        rtcLog('STUDENT REMOTE TRACK', describeTrack(event.track))
        if (!remote.getTracks().includes(event.track)) {
          remote.addTrack(event.track)
        }
        // New object so React re-renders the stage with both tracks.
        setTeacherStream(new MediaStream(remote.getTracks()))
      }

      peer.onicecandidate = (event) => {
        if (event.candidate) {
          send({ type: 'candidate', to: 'teacher', candidate: event.candidate })
        }
      }

      peer.addEventListener('connectionstatechange', () => {
        if (peerRef.current !== peer) return
        if (peer.connectionState === 'connected') {
          failedAttempts = 0
          window.setTimeout(() => logInboundStats(peer, 'student<-teacher'), 4000)
        } else if (peer.connectionState === 'failed' && !cancelled) {
          // ICE couldn't find a working path. Try a fresh connection a few
          // times rather than leaving both sides on a black tile forever.
          failedAttempts += 1
          if (failedAttempts <= 3) {
            rtcLog('WEBRTC', `connection failed, re-offering (attempt ${failedAttempts})`)
            window.setTimeout(() => {
              if (peerRef.current === peer && !cancelled) {
                offerToTeacher().catch((error) => console.error('Re-offer failed:', error))
              }
            }, 1000 * failedAttempts)
          } else {
            console.warn(
              '[WEBRTC] could not connect to the teacher. The networks likely need a TURN relay (VITE_TURN_URL / VITE_TURN_USERNAME / VITE_TURN_CREDENTIAL).',
            )
          }
        }
      })

      const offer = await peer.createOffer()
      await peer.setLocalDescription(offer)
      rtcLog('WEBRTC', 'student offer created', describeSdp(offer.sdp))
      send({ type: 'offer', to: 'teacher', offer })
    }

    const start = async () => {
      // 1. Own camera + microphone. Microphone starts muted.
      const media = await acquireLocalMedia({ video: true, audio: true })

      if (cancelled) {
        media.stream.getTracks().forEach((t) => t.stop())
        return
      }

      localStreamRef.current = media.stream
      cameraTrackRef.current = media.videoTrack
      micTrackRef.current = media.audioTrack
      if (media.audioTrack) {
        media.audioTrack.enabled = false
      }

      setCameraOn(Boolean(media.videoTrack))
      setMicOn(false)
      setMicAvailable(Boolean(media.audioTrack))
      setMediaNotice([media.cameraError, media.micError].filter(Boolean).join(' ') || null)

      if (videoRef.current) {
        // Preview (and the AI frame source) -- video only, muted.
        videoRef.current.srcObject = media.videoTrack ? new MediaStream([media.videoTrack]) : null
      }

      // 2. Authenticated classroom socket.
      ws = openClassroomSocket(classId)
      wsRef.current = ws

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
              // Reconnecting with an approval already granted: keep the
              // camera off (the server accepts it), rather than reporting
              // it on and then off again.
              cameraOffApprovedRef.current = Boolean(welcome.cameraOffApproved)
              if (welcome.cameraOffApproved && cameraTrackRef.current) {
                const track = cameraTrackRef.current
                cameraTrackRef.current = null
                track.stop()
                localStreamRef.current.removeTrack(track)
                if (videoRef.current) videoRef.current.srcObject = null
                setCameraOn(false)
              }
              setCameraRequest(welcome.cameraRequestPending ? 'pending' : 'idle')
              send(mediaState())
              if (welcome.participants.some((p) => p.role === 'teacher')) {
                await offerToTeacher()
              }
              break
            }
            case 'participant_joined':
              setParticipants((current) => [
                ...current.filter((p) => p.key !== message.participant.key),
                message.participant,
              ])
              // Teacher (re)joined: connect to them.
              if (message.participant.role === 'teacher') {
                await offerToTeacher()
              }
              break
            case 'participant_updated':
              setParticipants((current) =>
                current.map((p) => (p.key === message.participant.key ? message.participant : p)),
              )
              break
            case 'participant_left':
              setParticipants((current) => current.filter((p) => p.key !== message.key))
              if (String(message.key).startsWith('teacher:')) {
                closePeer()
              }
              break
            case 'answer': {
              const peer = peerRef.current
              if (!peer || peer.signalingState !== 'have-local-offer') {
                break
              }
              await peer.setRemoteDescription(new RTCSessionDescription(message.answer))
              rtcLog('WEBRTC', 'student answer received', describeSdp(message.answer?.sdp))
              for (const candidate of pendingCandidates) {
                try {
                  await peer.addIceCandidate(new RTCIceCandidate(candidate))
                } catch (error) {
                  console.warn('Failed to add queued ICE candidate:', error)
                }
              }
              pendingCandidates = []
              break
            }
            case 'candidate': {
              const peer = peerRef.current
              if (peer?.remoteDescription) {
                await peer.addIceCandidate(new RTCIceCandidate(message.candidate))
              } else {
                pendingCandidates.push(message.candidate)
              }
              break
            }
            case 'chat':
              setChat((current) => [...current, message as ClassChatMessage])
              if (panelRef.current !== 'chat') {
                setUnreadChat((n) => n + 1)
              }
              break
            case 'wb_open':
              setWhiteboardOpen(true)
              break
            case 'wb_close':
              setWhiteboardOpen(false)
              break
            case 'wb_stroke':
              strokesRef.current.push(message.stroke as WhiteboardStroke)
              setStrokeCount(strokesRef.current.length)
              break
            case 'wb_clear':
              strokesRef.current.length = 0
              setStrokeCount(0)
              setClearToken((t) => t + 1)
              break
            case 'class_ended':
              markClassEnded()
              break
            case 'camera_request_status':
              handleCameraRequestStatus(message.status as CameraRequestStatus)
              break
            case 'error':
              if (message.code === 401 || message.code === 403 || message.code === 409) {
                setAccessMessage(message.message ?? 'You are not authorized to join this class.')
                setAccess('denied')
              }
              break
          }
        } catch (error) {
          console.error('Student classroom message error:', error)
        }
      }

      ws.onclose = (event) => {
        if (event.code === WS_CLOSE_FORBIDDEN || event.code === WS_CLOSE_UNAUTHENTICATED || event.code === WS_CLOSE_REPLACED) {
          setAccessMessage((current) => current ?? 'You are not authorized to join this class.')
          setAccess('denied')
        }
      }
    }

    start().catch((error) => {
      console.error('Unable to start camera/classroom:', error)
      setMediaNotice('Unable to start the live classroom. Please reload the page.')
    })

    return () => {
      cancelled = true
      ws?.close()
      wsRef.current = null
      closePeer()
      localStreamRef.current.getTracks().forEach((track) => track.stop())
      cameraTrackRef.current = null
      micTrackRef.current = null
      setParticipants([])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [access, classId])

  // ---------------------------------------------------------------------------
  // CONTROLS
  // ---------------------------------------------------------------------------

  const toggleMic = async () => {
    const track = micTrackRef.current

    if (track) {
      track.enabled = !track.enabled
      setMicOn(track.enabled)
      send(mediaState({ mic: track.enabled }))
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const newTrack = stream.getAudioTracks()[0]
      micTrackRef.current = newTrack
      localStreamRef.current.addTrack(newTrack)
      await audioSenderRef.current?.replaceTrack(newTrack)
      setMicOn(true)
      setMicAvailable(true)
      setMediaNotice(null)
      send(mediaState({ mic: true }))
    } catch (error) {
      setMediaNotice(describeMediaError(error, 'microphone'))
    }
  }

  // Really stop the camera; the teacher sees a placeholder. While it's off
  // there are no frames to analyze, so AI monitoring pauses. Only reached
  // once the teacher has approved (the server refuses it otherwise).
  const turnCameraOff = async () => {
    const track = cameraTrackRef.current
    if (!track) return
    cameraTrackRef.current = null
    track.stop()
    localStreamRef.current.removeTrack(track)
    await videoSenderRef.current?.replaceTrack(null)
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
    send(mediaState({ camera: false }))
  }

  const turnCameraOn = async () => {
    try {
      const track = await acquireCameraTrack()
      cameraTrackRef.current = track
      localStreamRef.current.addTrack(track)
      await videoSenderRef.current?.replaceTrack(track)
      if (videoRef.current) videoRef.current.srcObject = new MediaStream([track])
      setCameraOn(true)
      setMediaNotice(null)
      // Turning it back on ends the approval (the server does the same).
      cameraOffApprovedRef.current = false
      setCameraRequest('idle')
      send(mediaState({ camera: true }))
    } catch (error) {
      setMediaNotice(describeMediaError(error, 'camera'))
    }
  }

  const toggleCamera = async () => {
    if (!cameraTrackRef.current) {
      await turnCameraOn()
      return
    }
    if (cameraOffApprovedRef.current) {
      await turnCameraOff()
      return
    }
    // The camera must stay on: ask the teacher instead. A request that is
    // already pending just keeps its status banner.
    if (cameraRequest !== 'pending') {
      setShowCameraRequestModal(true)
    }
  }

  const submitCameraRequest = (reason: string, note: string) => {
    setShowCameraRequestModal(false)
    send({ type: 'camera_off_request', reason, note })
  }

  const cancelCameraRequest = () => {
    send({ type: 'camera_off_cancel' })
  }

  // Server -> student status of the camera-off request.
  const handleCameraRequestStatus = (status: CameraRequestStatus) => {
    switch (status) {
      case 'pending':
        setCameraRequest('pending')
        break
      case 'approved':
        cameraOffApprovedRef.current = true
        setCameraRequest('approved')
        turnCameraOff().catch((error) => console.error('Unable to turn the camera off:', error))
        break
      case 'rejected':
        setCameraRequest('rejected')
        break
      case 'cancelled':
        setCameraRequest('idle')
        break
      case 'not_approved':
        setCameraRequest('idle')
        setMediaNotice('Your camera must stay on during class. Ask your teacher to turn it off.')
        break
      case 'invalid':
        setCameraRequest('idle')
        setMediaNotice('That camera-off request could not be sent. Please try again.')
        break
    }
  }

  const toggleHand = () => {
    const next = !handRaised
    setHandRaised(next)
    send(mediaState({ hand: next }))
  }

  const togglePanel = (next: Exclude<ClassroomPanel, 'none' | 'monitoring'> | 'monitoring') => {
    if (next === 'monitoring') return
    setPanel((value) => (value === next ? 'none' : next))
    if (next === 'chat') {
      setUnreadChat(0)
    }
  }

  // ---------------------------------------------------------------------------
  // REAL AI CAMERA ANALYSIS
  // ---------------------------------------------------------------------------

  useEffect(() => {
    // One frame at a time, always the NEWEST one: a frame is captured only
    // when the previous result is back (never queued), and the next one
    // goes out right away -- no waiting for a fixed interval tick. On
    // Render's free tier one frame takes ~1-8s, and overlapping requests
    // piled up server-side (results for frames sent long before, and a
    // backlog of concurrent inferences risking OOM restarts).
    // MIN_FRAME_INTERVAL_MS only caps the rate when the backend is fast.
    const MIN_FRAME_INTERVAL_MS = 350
    const IDLE_RETRY_MS = 250

    let stopped = false
    let timer: number | undefined

    const schedule = (delay: number) => {
      if (!stopped) {
        timer = window.setTimeout(analyzeNextFrame, delay)
      }
    }

    const analyzeNextFrame = async () => {
      if (classEndedRef.current || aiStoppedRef.current || accessRef.current !== 'allowed') {
        schedule(IDLE_RETRY_MS * 2)
        return
      }

      const video = videoRef.current

      // Camera/video is not ready yet (or the camera is off).
      if (!video || !video.srcObject || video.readyState < 2) {
        schedule(IDLE_RETRY_MS)
        return
      }

      const capturedAt = Date.now()
      const captureStart = performance.now()
      let requestStart = captureStart

      aiRequestInFlightRef.current = true

      try {
        // Create canvas once.
        if (!aiCanvasRef.current) {
          aiCanvasRef.current = document.createElement('canvas')
        }

        const canvas = aiCanvasRef.current

        canvas.width = 640
        canvas.height = 480

        const context = canvas.getContext('2d')

        if (!context) {
          return
        }

        // Copy current webcam frame into canvas.
        context.drawImage(video, 0, 0, canvas.width, canvas.height)

        // Convert frame to JPEG base64.
        const frame = canvas.toDataURL('image/jpeg', 0.7)

        // Uses the identity captured once at mount. The server checks it
        // against the token and rejects a mismatch.
        if (!realStudentId) {
          throw new Error('Student ID not found. Please login again.')
        }

        const token = sessionStorage.getItem('access_token') ?? ''

        requestStart = performance.now()

        const response = await fetch(`${API_BASE_URL}/ai/analyze-frame`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            frame,
            class_id: Number(classId),
            student_id: Number(realStudentId),
            student_name: realStudentName || 'Student',
          }),
        })

        const result = await response.json()
        const requestEnd = performance.now()

        // Temporary latency diagnostics (one line per analyzed frame).
        console.info('[AI TIMING]', {
          capture_encode_ms: Math.round(requestStart - captureStart),
          round_trip_ms: Math.round(requestEnd - requestStart),
          server: result.timing ?? null,
          alert: result.data?.active_alert ?? null,
        })

        if (response.status === 401 || response.status === 403) {
          // Not allowed (or logged out): stop, don't retry every tick.
          aiStoppedRef.current = true
          console.warn('AI monitoring refused:', result.error)
          return
        }

        // Teacher ended the session server-side (e.g. this tab was
        // backgrounded and missed the WebSocket 'class_ended' message).
        // Stop analyzing frames rather than keep posting into a dead
        // session.
        if (result.session_active === false) {
          markClassEnded()
          return
        }

        if (result.success) {
          // Send the real AI result to the teacher through the classroom
          // socket (the server stamps this student's identity on it).
          sendJson(wsRef.current, {
            type: 'ai_result',
            data: { ...result.data, client_timing: { captured_at: capturedAt } },
          })

          // Update student's own engagement indicator.
          if (typeof result.data?.engagement_score === 'number') {
            setMyEngagement(Math.max(0, Math.min(100, Number(result.data.engagement_score))))
          }

          // STUDENT AI ALERT -- uses the alert generated from THIS
          // student's camera.
          const activeAlert = result.data?.active_alert ?? null

          // Play the audible alert exactly once per NEW drowsiness
          // episode -- only when this poll's alert differs from the
          // previous poll's AND is 'drowsiness' (a transition INTO the
          // state, not every poll while still drowsy).
          if (activeAlert === 'drowsiness' && previousAlertRef.current !== 'drowsiness') {
            playDrowsinessAlertSound()
          }

          // Notify the teacher on a transition INTO an alert (never per
          // frame). The server builds the event from its own copy of this
          // result and applies a cooldown; see AI_ALERT in monitoring.py.
          if (activeAlert && activeAlert !== previousAlertRef.current) {
            sendJson(wsRef.current, { type: 'AI_ALERT' })
          }

          previousAlertRef.current = activeAlert

          if (activeAlert) {
            if (lastShownAlertRef.current !== activeAlert) {
              console.info('[AI TIMING] alert shown', {
                alert: activeAlert,
                capture_to_display_ms: Math.round(performance.now() - captureStart),
              })
            }
            lastShownAlertRef.current = activeAlert
            setAiAlert((previousAlert) => {
              if (previousAlert !== activeAlert) {
                setShowAiAlert(true)
              }

              return activeAlert
            })
          } else {
            lastShownAlertRef.current = null
            setAiAlert(null)
            setShowAiAlert(false)
          }
        } else {
          console.warn('AI analysis failed:', result.error)
        }
      } catch (error) {
        console.error('Unable to send frame to AI:', error)
      } finally {
        aiRequestInFlightRef.current = false
        // Next frame as soon as this one is done (the result is already
        // shown), rate-capped only when the backend answers very fast.
        schedule(Math.max(0, MIN_FRAME_INTERVAL_MS - (Date.now() - capturedAt)))
      }
    }

    schedule(0)

    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---------------------------------------------------------------------------
  // TIMER
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const timerInterval = window.setInterval(() => {
      setSeconds((value) => value + 1)
    }, 1000)

    return () => {
      window.clearInterval(timerInterval)
    }
  }, [])

  const timer = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  // ---------------------------------------------------------------------------
  // Leave automatically once the class has ended
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!classEnded) {
      return
    }

    const timeout = setTimeout(() => {
      navigate('/student')
    }, 3000)

    return () => clearTimeout(timeout)
  }, [classEnded, navigate])

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------

  if (access !== 'allowed') {
    return (
      <div className="flex h-screen items-center justify-center bg-[#080b12] p-6">
        {access === 'checking' ? (
          <div className="flex items-center gap-2 text-sm text-white/60">
            <Loader2 className="h-4 w-4 animate-spin" />
            Checking your access to this class…
          </div>
        ) : (
          <div className="max-w-md rounded-2xl bg-[#171923] p-6 text-center shadow-2xl" data-testid="access-denied">
            <ShieldAlert className="mx-auto h-8 w-8 text-critical-400" />
            <p className="mt-3 text-lg font-semibold text-white">You can't join this class</p>
            <p className="mt-1 text-sm text-white/60">{accessMessage ?? 'You are not authorized to join this class.'}</p>
            <button
              onClick={() => navigate('/student')}
              className="mt-4 rounded-lg bg-focus-500 px-4 py-2 text-sm font-medium text-white hover:bg-focus-600"
            >
              Back to dashboard
            </button>
          </div>
        )}
      </div>
    )
  }

  const teacherVideoOn = Boolean(teacher && (teacher.media.camera || teacher.media.screen) && teacherStream)

  return (
    <div className="flex h-screen flex-col bg-[#080b12]">
      {/* ============================================================
          CLASS ENDED
         ============================================================ */}

      {classEnded && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
          <div className="rounded-2xl bg-[#171923] p-6 text-center shadow-2xl">
            <p className="text-lg font-semibold text-white">This class has ended</p>
            <p className="mt-1 text-sm text-white/60">Taking you back to your dashboard…</p>
          </div>
        </div>
      )}

      {/* ============================================================
          AI MONITORING ALERT
         ============================================================ */}

      {showAiAlert && aiAlert && (
        <div className="fixed right-4 top-4 z-50 w-[360px] rounded-2xl border border-critical-500/30 bg-[#171923] p-4 shadow-2xl">
          <div className="flex items-start gap-3">
            {/* Alert icon */}

            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-critical-500/15">
              {aiAlert === 'phone_detected' && <Phone className="h-5 w-5 text-critical-400" />}
              {aiAlert === 'multiple_person' && <Users className="h-5 w-5 text-critical-400" />}
              {aiAlert === 'no_person_detected' && <UserX className="h-5 w-5 text-critical-400" />}
              {aiAlert === 'no_face_detected' && <UserX className="h-5 w-5 text-critical-400" />}
              {aiAlert === 'looking_away' && <EyeOff className="h-5 w-5 text-critical-400" />}
              {aiAlert === 'attention_drop_predicted' && <AlertTriangle className="h-5 w-5 text-critical-400" />}
              {aiAlert === 'drowsiness' && <AlertTriangle className="h-5 w-5 text-critical-400" />}
              {aiAlert === 'face_auth_failed' && <AlertTriangle className="h-5 w-5 text-critical-400" />}
            </div>

            {/* Alert message */}

            <div className="flex-1">
              <p className="text-sm font-semibold text-white">AI Monitoring Alert</p>

              <p className="mt-1 text-sm text-white/70">
                {aiAlert === 'phone_detected' && 'Please put away your mobile phone.'}
                {aiAlert === 'multiple_person' && 'Multiple people detected. Please remain alone in the classroom.'}
                {aiAlert === 'no_person_detected' && 'No person in front of camera. Please return to your seat.'}
                {aiAlert === 'no_face_detected' && 'Your face is not visible. Please face the camera.'}
                {aiAlert === 'looking_away' && 'Please look toward the screen.'}
                {aiAlert === 'attention_drop_predicted' && 'Your attention appears to be dropping. Please focus on the class.'}
                {aiAlert === 'drowsiness' && 'Signs of drowsiness were detected. Please stay attentive.'}
                {aiAlert === 'face_auth_failed' && 'Face authentication failed. Please position your face clearly in the camera.'}
              </p>
            </div>

            {/* Close notification */}

            <button
              type="button"
              onClick={() => setShowAiAlert(false)}
              className="text-white/40 transition-colors hover:text-white"
              aria-label="Dismiss alert"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* ============================================================
          HEADER
         ============================================================ */}

      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-xs font-medium text-critical-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-critical-500" />
            LIVE
          </span>

          <p className="text-sm font-semibold text-white">{classQuery.data?.title ?? 'Live class'}</p>
        </div>

        <div className="text-xs text-engaged-400">Face verified</div>
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

      {/* Camera-off request status */}

      {cameraRequest !== 'idle' && (
        <div
          className={`flex items-center justify-between gap-3 px-4 py-2 text-sm ${
            cameraRequest === 'rejected'
              ? 'bg-critical-500/15 text-critical-400'
              : cameraRequest === 'approved'
                ? 'bg-engaged-500/15 text-engaged-400'
                : 'bg-focus-500/15 text-white/80'
          }`}
          role="status"
          data-testid="camera-request-status"
        >
          <span className="flex items-center gap-2">
            {cameraRequest === 'pending' && <Loader2 className="h-4 w-4 shrink-0 animate-spin" />}
            {cameraRequest === 'pending' && 'Camera-off request sent. Waiting for teacher approval.'}
            {cameraRequest === 'approved' && 'Camera off approved.'}
            {cameraRequest === 'rejected' && 'Camera-off request rejected. Please keep your camera on.'}
          </span>
          {cameraRequest === 'pending' ? (
            <button onClick={cancelCameraRequest} className="text-xs underline underline-offset-2 hover:text-white">
              Cancel request
            </button>
          ) : (
            <button onClick={() => setCameraRequest('idle')} aria-label="Dismiss">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {showCameraRequestModal && (
        <CameraOffRequestModal
          onSubmit={submitCameraRequest}
          onClose={() => setShowCameraRequestModal(false)}
        />
      )}

      {/* ============================================================
          MAIN CLASSROOM
         ============================================================ */}

      <div className="flex flex-1 overflow-hidden">
        <div className="flex min-w-0 flex-1 flex-col gap-3 p-3">
          {/* Teacher (camera / screen share), or the whiteboard when open */}

          <div className="relative min-h-[240px] flex-1">
            {whiteboardOpen ? (
              <div className="flex h-full gap-3">
                <div className="min-w-0 flex-1">
                  <Whiteboard strokes={strokesRef.current} strokeCount={strokeCount} clearToken={clearToken} editable={false} />
                </div>
                <div className="hidden w-64 shrink-0 lg:block">
                  <div className="aspect-video">
                    <StageTile
                      name={teacher?.name ?? 'Teacher'}
                      label={`${teacher?.name ?? 'Teacher'} (Teacher)`}
                      stream={teacherStream}
                      videoOn={teacherVideoOn}
                      micOn={Boolean(teacher?.media.mic)}
                      screenSharing={Boolean(teacher?.media.screen)}
                      muted={false}
                      testId="teacher-remote-video"
                    />
                  </div>
                </div>
              </div>
            ) : teacher ? (
              <StageTile
                name={teacher.name}
                label={`${teacher.name} (Teacher)`}
                stream={teacherStream}
                videoOn={teacherVideoOn}
                micOn={teacher.media.mic}
                screenSharing={teacher.media.screen}
                muted={false}
                testId="teacher-remote-video"
              />
            ) : (
              <div className="flex h-full items-center justify-center rounded-2xl bg-gradient-to-br from-focus-900/60 to-[#0f131e] text-sm text-white/60">
                Waiting for the teacher to connect…
              </div>
            )}
          </div>

          {/* ========================================================
              SELF TILE + ENGAGEMENT
             ======================================================== */}

          <div className="flex items-center justify-between rounded-2xl bg-[#12151f] p-3">
            <div className="flex items-center gap-3">
              <div className="relative h-24 w-32 overflow-hidden rounded-xl bg-[#161b28]">
                <video
                  ref={videoRef}
                  data-testid="student-self-video"
                  autoPlay
                  playsInline
                  muted
                  className={`h-full w-full -scale-x-100 object-cover ${cameraOn ? '' : 'invisible'}`}
                />
                {!cameraOn && (
                  <div className="absolute inset-0 flex items-center justify-center text-[11px] text-white/50">Camera off</div>
                )}
              </div>

              <div>
                <p className="text-sm font-medium text-white">{realStudentName} (You)</p>

                <p className="text-xs text-white/50">
                  {cameraOn ? 'Camera on' : 'Camera off'} · {micOn ? 'Mic on' : 'Mic muted'}
                  {handRaised && ' · Hand raised'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs text-white/50">Your engagement</p>

                <Badge variant={myEngagement >= 70 ? 'engaged' : myEngagement >= 40 ? 'attention' : 'critical'}>
                  {myEngagement >= 70 ? 'Focused' : myEngagement >= 40 ? 'Drifting' : 'Needs attention'}
                </Badge>
              </div>

              <ConfidenceRing value={myEngagement} size={48} strokeWidth={5} />
            </div>
          </div>
        </div>

        {/* ==========================================================
            SIDE PANEL
           ========================================================== */}

        {panel !== 'none' && (
          <div className="w-[320px] shrink-0 border-l border-white/10 bg-[#0f131e]">
            {panel === 'participants' && <ParticipantsPanel participants={participants} selfKey={selfKey} />}

            {panel === 'chat' && (
              <ChatPanel
                messages={chat}
                selfKey={selfKey}
                disabled={!selfKey}
                onSend={(text) => send({ type: 'chat', text })}
              />
            )}
          </div>
        )}
      </div>

      {/* ============================================================
          CLASSROOM CONTROLS
         ============================================================ */}

      <ClassroomControls
        role="student"
        micOn={micOn}
        cameraOn={cameraOn}
        micAvailable={micAvailable || !micTrackRef.current}
        handRaised={handRaised}
        recording={false}
        panel={panel}
        unreadChat={unreadChat}
        onToggleMic={toggleMic}
        onToggleCamera={toggleCamera}
        onToggleHand={toggleHand}
        onTogglePanel={togglePanel}
        onLeave={() => navigate('/student')}
        timer={timer}
      />
    </div>
  )
}
