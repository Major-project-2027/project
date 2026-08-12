import { useRef } from 'react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import {
  AlertTriangle,
  Phone,
  Users,
  EyeOff,
  X,
  ScreenShare,
} from 'lucide-react'

import { ParticipantsPanel } from '@/components/classroom/ParticipantsPanel'
import { ChatPanel } from '@/components/classroom/ChatPanel'
import { ClassroomControls } from '@/components/classroom/ClassroomControls'
import { Avatar } from '@/components/ui/Avatar'
import { ConfidenceRing } from '@/components/monitoring/ConfidenceRing'
import { Badge } from '@/components/ui/Badge'

import { currentStudent } from '@/mocks/data'
import { generateLiveStudents } from '@/mocks/data'
import { classesApi } from '@/services/api/endpoints'

type SidePanel = 'none' | 'participants' | 'chat'

export function StudentLiveClassroomPage() {
  const navigate = useNavigate()
  const { classId } = useParams()

  // Real identity of the logged-in student -- must match what /ai/analyze-frame
  // is sent so the teacher's WebRTC tile and AI-monitoring tile merge into one
  // student instead of appearing as two separate (mock vs. real) entries.
  const realStudentId = localStorage.getItem('user_id') ?? currentStudent.id
  const realStudentName = localStorage.getItem('user_name') ?? currentStudent.name

  useEffect(() => {
  const joinClass = async () => {
    const token = localStorage.getItem('access_token')

    if (!token || !classId) {
      return
    }

    try {
      const response = await fetch(
        'http://127.0.0.1:5000/join-class',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            class_code: classId,
          }),
        },
      )

      const result = await response.json()

      if (!response.ok || !result.success) {
        console.error('Unable to join class:', result.error)
      } else {
        console.log('Class joined successfully')
      }
    } catch (error) {
      console.error('Join class request failed:', error)
    }
  }

  joinClass()
}, [classId])
  const classQuery = useQuery({
    queryKey: ['class', classId],
    queryFn: () => classesApi.get(classId ?? ''),
  })

  const [micOn, setMicOn] = useState(false)
  const [cameraOn, setCameraOn] = useState(true)
  const [handRaised, setHandRaised] = useState(false)
  const [panel, setPanel] = useState<SidePanel>('none')
  const [seconds, setSeconds] = useState(0)
  const [myEngagement, setMyEngagement] = useState(74)

  const [aiAlert, setAiAlert] = useState<string | null>(null)
  const [showAiAlert, setShowAiAlert] = useState(false)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const aiCanvasRef = useRef<HTMLCanvasElement | null>(null)

  const peerRef = useRef<RTCPeerConnection | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const students = generateLiveStudents(15)

  // ---------------------------------------------------------------------------
  // CAMERA + WEBRTC
  // ---------------------------------------------------------------------------

  useEffect(() => {
    let stream: MediaStream | null = null

    async function startCameraAndWebRTC() {
      try {
        // ------------------------------------------------------------
        // 1. Open student's camera
        // ------------------------------------------------------------

        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        })

        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }

        // ------------------------------------------------------------
        // 2. Connect to signaling server
        // ------------------------------------------------------------

        const ws = new WebSocket(
          `ws://127.0.0.1:8000/ws/classes/${classId}/signaling`,
        )

        wsRef.current = ws

        ws.onopen = async () => {
          console.log('Student signaling connected')

          // ----------------------------------------------------------
          // 3. Create WebRTC peer connection
          // ----------------------------------------------------------

          const peer = new RTCPeerConnection({
            iceServers: [
              {
                urls: 'stun:stun.l.google.com:19302',
              },
            ],
          })

          peerRef.current = peer

          // ----------------------------------------------------------
          // 4. Store ICE candidates that arrive before the answer
          // ----------------------------------------------------------

          const pendingCandidates: RTCIceCandidate[] = []

          // ----------------------------------------------------------
          // 5. Add camera tracks
          // ----------------------------------------------------------

          stream?.getTracks().forEach((track) => {
            peer.addTrack(track, stream!)
          })

          // ----------------------------------------------------------
          // 6. Send ICE candidates
          // ----------------------------------------------------------

          peer.onicecandidate = (event) => {
            if (
              event.candidate &&
              ws.readyState === WebSocket.OPEN
            ) {
              ws.send(
                JSON.stringify({
                  type: 'candidate',
                  role: 'student',
                  studentId: realStudentId,
                  candidate: event.candidate,
                }),
              )
            }
          }

          // ----------------------------------------------------------
          // 7. Create offer
          // ----------------------------------------------------------

          const offer = await peer.createOffer()

          await peer.setLocalDescription(offer)

          ws.send(
            JSON.stringify({
              type: 'offer',
              role: 'student',
              studentId: realStudentId,
              studentName: realStudentName,
              offer,
            }),
          )

          console.log('Student WebRTC offer sent')

          // ----------------------------------------------------------
          // 8. Receive signaling messages
          // ----------------------------------------------------------

          ws.onmessage = async (event) => {
            try {
              const message = JSON.parse(event.data)

              // ------------------------------------------------------
              // Teacher sent WebRTC answer
              // ------------------------------------------------------

              if (message.type === 'answer') {
                // Prevent duplicate / late answers.
                if (peer.signalingState !== 'have-local-offer') {
                  console.warn(
                    'Ignoring duplicate/late WebRTC answer. Current state:',
                    peer.signalingState,
                  )

                  return
                }

                await peer.setRemoteDescription(
                  new RTCSessionDescription(message.answer),
                )

                console.log('Teacher WebRTC answer received')

                // ----------------------------------------------------
                // Add ICE candidates that arrived before the answer.
                // ----------------------------------------------------

                for (const candidate of pendingCandidates) {
                  try {
                    await peer.addIceCandidate(candidate)
                  } catch (error) {
                    console.warn(
                      'Failed to add queued ICE candidate:',
                      error,
                    )
                  }
                }

                pendingCandidates.length = 0
              }

              // ------------------------------------------------------
              // Teacher sent ICE candidate
              // ------------------------------------------------------

              if (message.type === 'candidate') {
                const candidate = new RTCIceCandidate(
                  message.candidate,
                )

                // Remote description already exists.
                if (peer.remoteDescription) {
                  await peer.addIceCandidate(candidate)
                } else {
                  // Answer has not arrived yet.
                  pendingCandidates.push(candidate)

                  console.log(
                    'ICE candidate queued until teacher answer arrives',
                  )
                }
              }
            } catch (error) {
              console.error(
                'Student signaling message error:',
                error,
              )
            }
          }
        }

        ws.onerror = (error) => {
          console.error(
            'Student signaling error:',
            error,
          )
        }

        ws.onclose = () => {
          console.log('Student signaling disconnected')
        }
      } catch (error) {
        console.error(
          'Unable to start camera/WebRTC:',
          error,
        )
      }
    }

    startCameraAndWebRTC()

    return () => {
      wsRef.current?.close()
      peerRef.current?.close()

      stream?.getTracks().forEach((track) => {
        track.stop()
      })
    }
  }, [classId])

  // ---------------------------------------------------------------------------
  // REAL AI CAMERA ANALYSIS
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const interval = setInterval(async () => {
      const video = videoRef.current

      // Camera/video is not ready yet.
      if (!video || video.readyState < 2) {
        return
      }

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
        context.drawImage(
          video,
          0,
          0,
          canvas.width,
          canvas.height,
        )

        // Convert frame to JPEG base64.
        const frame = canvas.toDataURL(
          'image/jpeg',
          0.7,
        )

        // Send frame to FastAPI AI endpoint. Uses the identity captured once
        // at mount (realStudentId/realStudentName) rather than re-reading
        // localStorage on every tick -- localStorage is shared across tabs,
        // so a fresh read here would let an unrelated login in another tab
        // silently hijack this tab's identity mid-session.
        if (!realStudentId) {
          throw new Error('Student ID not found. Please login again.')
        }

        const response = await fetch(
          'http://127.0.0.1:8000/ai/analyze-frame',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              frame,
              class_id: Number(classId),
              student_id: Number(realStudentId),
              student_name: realStudentName || 'Student',
            }),
          },
        )

        const result = await response.json()

        if (result.success) {
          console.log(
            'REAL AI RESULT:',
            result.data,
          )

          // ----------------------------------------------------------
          // Send the real AI result to the teacher
          // through the existing classroom WebSocket.
          // ----------------------------------------------------------

          if (
            wsRef.current?.readyState === WebSocket.OPEN
          ) {
            wsRef.current.send(
              JSON.stringify({
                type: 'ai_result',
                role: 'student',
                studentId: realStudentId,
                studentName: realStudentName,
                data: result.data,
              }),
            )
          }

          // ----------------------------------------------------------
          // Update student's own engagement indicator.
          // ----------------------------------------------------------

          if (
            typeof result.data?.engagement_score === 'number'
          ) {
            setMyEngagement(
              Math.max(
                0,
                Math.min(
                  100,
                  Number(
                    result.data.engagement_score,
                  ),
                ),
              ),
            )
          }

          // ----------------------------------------------------------
          // STUDENT AI ALERT
          // Uses the alert generated from THIS student's camera.
          // ----------------------------------------------------------

          const activeAlert =
            result.data?.active_alert ?? null

          if (activeAlert) {
            setAiAlert((previousAlert) => {
              if (
                previousAlert !== activeAlert
              ) {
                setShowAiAlert(true)
              }

              return activeAlert
            })
          } else {
            setAiAlert(null)
            setShowAiAlert(false)
          }
        } else {
          console.warn(
            'AI analysis failed:',
            result.error,
          )
        }
      } catch (error) {
        console.error(
          'Unable to send frame to AI:',
          error,
        )
      }
    }, 2000)

    return () => {
      clearInterval(interval)
    }
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

  const timer = `${String(
    Math.floor(seconds / 60),
  ).padStart(2, '0')}:${String(
    seconds % 60,
  ).padStart(2, '0')}`

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------

  return (
    <>
      {/* ============================================================
          AI MONITORING ALERT
         ============================================================ */}

      {showAiAlert && aiAlert && (
        <div className="fixed right-4 top-4 z-50 w-[360px] rounded-2xl border border-critical-500/30 bg-[#171923] p-4 shadow-2xl">

          <div className="flex items-start gap-3">

            {/* Alert icon */}

            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-critical-500/15">

              {aiAlert === 'phone_detected' && (
                <Phone className="h-5 w-5 text-critical-400" />
              )}

              {aiAlert === 'multiple_person' && (
                <Users className="h-5 w-5 text-critical-400" />
              )}

              {aiAlert === 'looking_away' && (
                <EyeOff className="h-5 w-5 text-critical-400" />
              )}

              {aiAlert === 'attention_drop_predicted' && (
                <AlertTriangle className="h-5 w-5 text-critical-400" />
              )}

              {aiAlert === 'drowsiness' && (
                <AlertTriangle className="h-5 w-5 text-critical-400" />
              )}

              {aiAlert === 'face_auth_failed' && (
                <AlertTriangle className="h-5 w-5 text-critical-400" />
              )}

            </div>

            {/* Alert message */}

            <div className="flex-1">

              <p className="text-sm font-semibold text-white">
                AI Monitoring Alert
              </p>

              <p className="mt-1 text-sm text-white/70">

                {aiAlert === 'phone_detected' &&
                  'Please put away your mobile phone.'}

                {aiAlert === 'multiple_person' &&
                  'Multiple people detected. Please remain alone in the classroom.'}

                {aiAlert === 'looking_away' &&
                  'Please look toward the screen.'}

                {aiAlert === 'attention_drop_predicted' &&
                  'Your attention appears to be dropping. Please focus on the class.'}

                {aiAlert === 'drowsiness' &&
                  'Signs of drowsiness were detected. Please stay attentive.'}

                {aiAlert === 'face_auth_failed' &&
                  'Face authentication failed. Please position your face clearly in the camera.'}

              </p>

            </div>

            {/* Close notification */}

            <button
              type="button"
              onClick={() => setShowAiAlert(false)}
              className="text-white/40 transition-colors hover:text-white"
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

          <p className="text-sm font-semibold text-white">
            {classQuery.data?.title ?? 'Live class'}
          </p>

        </div>

        <div>
          Face verified
        </div>

      </div>

      {/* ============================================================
          MAIN CLASSROOM
         ============================================================ */}

      <div className="flex flex-1 overflow-hidden">

        <div className="flex flex-1 flex-col gap-3 p-3">

          {/* Teacher's video, large */}

          <div className="relative flex flex-1 items-center justify-center rounded-2xl bg-gradient-to-br from-focus-900/60 to-[#0f131e]">

            <Avatar
              name="Dr. Kavita Rao"
              size={72}
            />

            <div className="absolute left-3 top-3 rounded-md bg-black/50 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
              Dr. Kavita Rao (Teacher)
            </div>

            <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md bg-black/50 px-2.5 py-1 text-xs text-white backdrop-blur">

              <ScreenShare className="h-3.5 w-3.5" />

              Screen not shared

            </div>

          </div>

          {/* ========================================================
              SELF TILE + ENGAGEMENT
             ======================================================== */}

          <div className="flex items-center justify-between rounded-2xl bg-[#12151f] p-3">

            <div className="flex items-center gap-3">

              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="h-24 w-32 rounded-xl object-cover"
              />

              <div>

                <p className="text-sm font-medium text-white">
                  {realStudentName} (You)
                </p>

                <p className="text-xs text-white/50">

                  {cameraOn
                    ? 'Camera on'
                    : 'Camera off'}{' '}

                  ·{' '}

                  {micOn
                    ? 'Mic on'
                    : 'Mic muted'}

                </p>

              </div>

            </div>

            <div className="flex items-center gap-3">

              <div className="text-right">

                <p className="text-xs text-white/50">
                  Your engagement
                </p>

                <Badge
                  variant={
                    myEngagement >= 70
                      ? 'engaged'
                      : myEngagement >= 40
                        ? 'attention'
                        : 'critical'
                  }
                >

                  {myEngagement >= 70
                    ? 'Focused'
                    : myEngagement >= 40
                      ? 'Drifting'
                      : 'Needs attention'}

                </Badge>

              </div>

              <ConfidenceRing
                value={myEngagement}
                size={48}
                strokeWidth={5}
              />

            </div>

          </div>

        </div>

        {/* ==========================================================
            SIDE PANEL
           ========================================================== */}

        {panel !== 'none' && (
          <div className="w-[320px] shrink-0 border-l border-white/10 bg-[#0f131e]">

            {panel === 'participants' && (
              <ParticipantsPanel
                students={students}
              />
            )}

            {panel === 'chat' && (
              <ChatPanel />
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

        handRaised={handRaised}

        screenSharing={false}

        recording={false}

        onToggleMic={() =>
          setMicOn((value) => !value)
        }

        onToggleCamera={() =>
          setCameraOn((value) => !value)
        }

        onToggleHand={() =>
          setHandRaised((value) => !value)
        }

        onToggleScreenShare={() => {}}

        onToggleParticipants={() =>
          setPanel((value) =>
            value === 'participants'
              ? 'none'
              : 'participants',
          )
        }

        onToggleChat={() =>
          setPanel((value) =>
            value === 'chat'
              ? 'none'
              : 'chat',
          )
        }

        onLeave={() =>
          navigate('/student')
        }

        timer={timer}
      />

    </>
  )
}
