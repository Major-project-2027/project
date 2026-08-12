import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, X, ShieldAlert } from 'lucide-react'

import { VideoTile } from '@/components/classroom/VideoTile'
import { ParticipantsPanel } from '@/components/classroom/ParticipantsPanel'
import { ChatPanel } from '@/components/classroom/ChatPanel'
import { ClassroomControls } from '@/components/classroom/ClassroomControls'
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

import {
  recordStudentEngagement,
} from '@/mocks/data'

import { Badge } from '@/components/ui/Badge'
import type { StudentLiveState } from '@/types/domain'

type SidePanel =
  | 'none'
  | 'participants'
  | 'chat'
  | 'monitoring'

const ALERT_LABEL: Record<string, string> = {
  looking_away: 'Looking away from screen',
  drowsiness: 'Signs of drowsiness detected',
  phone_detected: 'Mobile phone detected',
  multiple_person: 'A second person detected',
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

  let activeAlert = null

  if (phoneDetected) {
    activeAlert = 'phone_detected'
  } else if (personCount > 1) {
    activeAlert = 'multiple_person'
  } else if (
    !['center', 'forward'].includes(
      gaze.toLowerCase(),
    )
  ) {
    activeAlert = 'looking_away'
  }

  let cognitiveState = 'focused'

  if (engagement < 40) {
    cognitiveState = 'drowsy'
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

    history: [
      ...(existing?.history ?? []).slice(-19),
      engagement,
    ],
  }
}

export function TeacherLiveClassroomPage() {
  const { classId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [micOn, setMicOn] = useState(true)
  const [cameraOn, setCameraOn] = useState(true)
  const [screenSharing, setScreenSharing] = useState(false)

  const [panel, setPanel] = useState<SidePanel>('monitoring')

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [dismissedAlert, setDismissedAlert] = useState(false)

  // -------------------------------------------------------------------------
  // WebRTC / signaling refs
  // -------------------------------------------------------------------------

  const alertedIds = useRef<Set<string>>(new Set())

  const signalingRef = useRef<WebSocket | null>(null)

  const peersRef = useRef<Record<string, RTCPeerConnection>>({})

  const pendingCandidatesRef = useRef<
    Record<string, RTCIceCandidateInit[]>
  >({})

  // -------------------------------------------------------------------------
  // Students received through WebRTC
  // -------------------------------------------------------------------------

  const [connectedStudents, setConnectedStudents] = useState<
    StudentLiveState[]
  >([])

  // -------------------------------------------------------------------------
  // API data
  // -------------------------------------------------------------------------

  const classQuery = useQuery({
    queryKey: ['class', classId],
    queryFn: () => classesApi.get(classId ?? ''),
  })

  const studentsQuery = useQuery({
  queryKey: ['live-students', classId],
  queryFn: monitoringApi.liveStudents,
  refetchInterval: 8000,
})

  const apiStudents = studentsQuery.data ?? []

  // -------------------------------------------------------------------------
  // Merge AI monitoring students + WebRTC-connected students
  // -------------------------------------------------------------------------

  const students: StudentLiveState[] = (() => {
    const merged = new Map<string, StudentLiveState>()

    // First add AI/backend students.
    for (const student of apiStudents) {
      merged.set(student.studentId, student)
    }

    // Then add/update students connected through WebRTC.
    for (const student of connectedStudents) {
      const existing = merged.get(student.studentId)

      if (existing) {
        merged.set(student.studentId, {
          ...student,
          ...existing,
          cameraOn: true,
        })
      } else {
        merged.set(student.studentId, student)
      }
    }

    return Array.from(merged.values())
  })()

  const selected =
    students.find((s) => s.studentId === selectedId) ??
    students[0]

  const avgEngagement = Math.round(
    students.reduce(
      (total, student) => total + student.currentEngagement,
      0,
    ) / (students.length || 1),
  )

  const activeAlerts = students.filter(
    (student) => student.activeAlert,
  )

  // -------------------------------------------------------------------------
  // End class
  // -------------------------------------------------------------------------

  const endMutation = useMutation({
  mutationFn: () => classesApi.end(classId ?? ''),

  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: ['classes'],
    })

    queryClient.invalidateQueries({
      queryKey: ['attendance'],
    })

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
  // WEBRTC SIGNALING
  // =========================================================================

  useEffect(() => {
    if (!classId) {
      return
    }

    const ws = new WebSocket(
      `ws://127.0.0.1:8000/ws/classes/${classId}/signaling`,
    )

    signalingRef.current = ws

    // -----------------------------------------------------------------------
    // WebSocket connected
    // -----------------------------------------------------------------------

    ws.onopen = () => {
      console.log('Teacher signaling connected')
    }

    // -----------------------------------------------------------------------
    // Messages from students
    // -----------------------------------------------------------------------

    ws.onmessage = async (event) => {
  try {
    const message = JSON.parse(event.data)

    // ===================================================================
    // REAL AI RESULT FROM STUDENT
    // ===================================================================

    if (message.type === 'ai_result') {
      const studentId = message.studentId
      const studentName =
        message.studentName ?? 'Student'

      console.log(
        'REAL AI RESULT FROM STUDENT:',
        studentId,
        message.data,
      )

      setConnectedStudents((current) => {
        const existing = current.find(
          (student) =>
            student.studentId === studentId,
        )

        const updatedStudent =
          convertAIResultToStudent(
            message,
            existing,
          ) as StudentLiveState
        // ---------------------------------------------------------------
// RECORD REAL ENGAGEMENT FOR ATTENDANCE
// ---------------------------------------------------------------

if (
  classId &&
  classQuery.data?.status === 'live'
) {
  recordStudentEngagement(
    classId,
    studentId,
    studentName,
    updatedStudent.currentEngagement ?? 0,
  )
}

        // ---------------------------------------------------------------
        // Student already connected through WebRTC.
        // ---------------------------------------------------------------

        if (existing) {
          return current.map((student) =>
            student.studentId === studentId
              ? {
                  ...student,
                  ...updatedStudent,
                  cameraOn: true,
                }
              : student,
          )
        }

        // ---------------------------------------------------------------
        // AI result arrived before WebRTC entry.
        // Create the student so the teacher still sees the AI data.
        // ---------------------------------------------------------------

        const newStudent: StudentLiveState = {
          ...updatedStudent,

          studentId,

          studentName,

          cameraOn: true,
          micOn: false,
          handRaised: false,

          currentEngagement:
            updatedStudent.currentEngagement ?? 0,

          currentEmotion:
            updatedStudent.currentEmotion ?? 'neutral',

          cognitiveState:
            updatedStudent.cognitiveState ?? 'focused',

          authenticated:
            updatedStudent.authenticated ?? false,

          history:
            updatedStudent.history ?? [
              updatedStudent.currentEngagement ?? 0,
            ],
        }

        return [
          ...current,
          newStudent,
        ]
      })

      return
    }

    // ===================================================================
    // STUDENT OFFER
    // ===================================================================

    if (message.type === 'offer') {
      const studentId = message.studentId
      const studentName =
        message.studentName ?? 'Student'

      console.log(
        'WebRTC offer received from student:',
        studentId,
      )

      // Close an old peer if one somehow exists.
      const oldPeer =
        peersRef.current[studentId]

      if (oldPeer) {
        oldPeer.close()
      }

      // Create new peer connection.
      const peer = new RTCPeerConnection({
        iceServers: [
          {
            urls:
              'stun:stun.l.google.com:19302',
          },
        ],
      })

      peersRef.current[studentId] = peer

      pendingCandidatesRef.current[
        studentId
      ] = []

      // ---------------------------------------------------------------
      // Create student entry immediately.
      // This makes VideoTile render before ontrack fires.
      // ---------------------------------------------------------------

      setConnectedStudents((current) => {
        const alreadyExists =
          current.some(
            (student) =>
              student.studentId === studentId,
          )

        if (alreadyExists) {
          return current
        }

        const newStudent:
          StudentLiveState = {
          studentId,
          studentName,

          cameraOn: true,
          micOn: false,
          handRaised: false,

          currentEngagement: 74,
          currentEmotion: 'neutral',
          cognitiveState: 'focused',

          authenticated: true,

          activeAlert: undefined,

          history: [74],
        }

        return [
          ...current,
          newStudent,
        ]
      })

      // ---------------------------------------------------------------
      // Receive student's camera
      // ---------------------------------------------------------------

      peer.ontrack = (event) => {
        console.log(
          'Remote student camera received:',
          studentId,
        )

        const stream =
          event.streams[0]

        if (!stream) {
          return
        }

        const video =
          document.getElementById(
            `student-video-${studentId}`,
          ) as HTMLVideoElement | null

        if (video) {
          video.srcObject = stream

          video.play().catch(() => {})
        }

        // Make sure student remains visible.
        setConnectedStudents(
          (current) =>
            current.map((student) =>
              student.studentId ===
              studentId
                ? {
                    ...student,
                    cameraOn: true,
                  }
                : student,
            ),
        )
      }

      // ---------------------------------------------------------------
      // Send ICE candidates to student
      // ---------------------------------------------------------------

      peer.onicecandidate = (
        event,
      ) => {
        if (
          event.candidate &&
          ws.readyState ===
            WebSocket.OPEN
        ) {
          ws.send(
            JSON.stringify({
              type: 'candidate',
              role: 'teacher',
              studentId,
              candidate:
                event.candidate,
            }),
          )
        }
      }

      // ---------------------------------------------------------------
      // Connection state
      // ---------------------------------------------------------------

      peer.onconnectionstatechange =
        () => {
          console.log(
            `Student ${studentId} WebRTC state:`,
            peer.connectionState,
          )

          if (
            peer.connectionState ===
              'failed' ||
            peer.connectionState ===
              'closed' ||
            peer.connectionState ===
              'disconnected'
          ) {
            setConnectedStudents(
              (current) =>
                current.filter(
                  (student) =>
                    student.studentId !==
                    studentId,
                ),
            )

            delete peersRef.current[
              studentId
            ]
          }
        }

      // ---------------------------------------------------------------
      // Receive student's offer
      // ---------------------------------------------------------------

      await peer.setRemoteDescription(
        new RTCSessionDescription(
          message.offer,
        ),
      )

      // ---------------------------------------------------------------
      // Add any ICE candidates that arrived early
      // ---------------------------------------------------------------

      const pending =
        pendingCandidatesRef.current[
          studentId
        ] ?? []

      for (const candidate of pending) {
        try {
          await peer.addIceCandidate(
            new RTCIceCandidate(
              candidate,
            ),
          )
        } catch (error) {
          console.error(
            'Failed to add queued ICE candidate:',
            error,
          )
        }
      }

      pendingCandidatesRef.current[
        studentId
      ] = []

      // ---------------------------------------------------------------
      // Create answer
      // ---------------------------------------------------------------

      const answer =
        await peer.createAnswer()

      await peer.setLocalDescription(
        answer,
      )

      if (
        ws.readyState ===
        WebSocket.OPEN
      ) {
        ws.send(
          JSON.stringify({
            type: 'answer',
            role: 'teacher',
            studentId,
            answer,
          }),
        )
      }

      console.log(
        'WebRTC answer sent to student:',
        studentId,
      )

      return
    }

    // ===================================================================
    // STUDENT ICE CANDIDATE
    // ===================================================================

    if (message.type === 'candidate') {
      const studentId =
        message.studentId

      const peer =
        peersRef.current[
          studentId
        ]

      if (!peer) {
        return
      }

      const candidate =
        message.candidate

      // If remote description is not ready yet,
      // queue the candidate.
      if (
        !peer.remoteDescription
      ) {
        if (
          !pendingCandidatesRef
            .current[studentId]
        ) {
          pendingCandidatesRef.current[
            studentId
          ] = []
        }

        pendingCandidatesRef.current[
          studentId
        ].push(candidate)

        console.log(
          'ICE candidate queued until remote description arrives:',
          studentId,
        )

        return
      }

      try {
        await peer.addIceCandidate(
          new RTCIceCandidate(
            candidate,
          ),
        )
      } catch (error) {
        console.error(
          'Failed to add ICE candidate:',
          error,
        )
      }
    }
  } catch (error) {
    console.error(
      'Teacher signaling message error:',
      error,
    )
  }
}

    // -----------------------------------------------------------------------
    // WebSocket error
    // -----------------------------------------------------------------------

    ws.onerror = (error) => {
      console.error(
        'Teacher signaling error:',
        error,
      )
    }

    // -----------------------------------------------------------------------
    // Cleanup
    // -----------------------------------------------------------------------

    return () => {
      ws.close()

      Object.values(peersRef.current).forEach(
        (peer) => peer.close(),
      )

      peersRef.current = {}

      pendingCandidatesRef.current = {}

      setConnectedStudents([])
    }
  }, [classId])

  // =========================================================================
  // ALERT TOASTS
  // =========================================================================

  // =========================================================================
// ALERT TOASTS
// =========================================================================

useEffect(() => {
  const currentlyActive = new Set<string>()

  for (const student of students) {
    if (!student.activeAlert) {
      continue
    }

    const alertKey =
      `${student.studentId}-${student.activeAlert}`

    currentlyActive.add(alertKey)

    // ---------------------------------------------------------------
    // Only show a toast when this alert is newly detected.
    // ---------------------------------------------------------------

    if (!alertedIds.current.has(alertKey)) {
      alertedIds.current.add(alertKey)

      pushAlertToast({
        studentName: student.studentName,

        message:
          ALERT_LABEL[student.activeAlert] ??
          'Attention issue detected',

        severity:
          student.activeAlert === 'phone_detected' ||
          student.activeAlert === 'multiple_person'
            ? 'critical'
            : 'warning',
      })
    }
  }

  // ---------------------------------------------------------------
  // Remove cleared alerts from the memory.
  //
  // This allows the same alert to trigger again later.
  // ---------------------------------------------------------------

  for (const key of alertedIds.current) {
    if (!currentlyActive.has(key)) {
      alertedIds.current.delete(key)
    }
  }
}, [students])

  const timer = `${String(
    Math.floor(seconds / 60),
  ).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

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

          <Badge
            variant="neutral"
            className="bg-white/10 text-white"
          >
            {students.length} students
          </Badge>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 sm:flex">
            <ConfidenceRing
              value={avgEngagement}
              size={36}
              strokeWidth={4}
            />

            <span className="text-xs text-white/60">
              class avg.
            </span>
          </div>
        </div>
      </div>

      {/* Alert banner */}

      {activeAlerts.length > 0 && !dismissedAlert && (
        <div className="flex items-center justify-between gap-3 bg-critical-500/15 px-4 py-2 text-sm text-critical-300">
          <span className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />

            {activeAlerts.length} student(s) currently need
            attention — {activeAlerts[0].studentName} (
            {ALERT_LABEL[
              activeAlerts[0].activeAlert ?? ''
            ] ?? 'flagged'}
            )
          </span>

          <button
            onClick={() => setDismissedAlert(true)}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Main content */}

      <div className="flex flex-1 overflow-hidden">
        {/* Video grid */}

        <div className="flex-1 overflow-y-auto p-3">
          {students.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center text-white/50">
                <p className="text-sm">
                  Waiting for students to join...
                </p>

                <p className="mt-1 text-xs">
                  WebRTC connection is ready.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {students.map((student) => (
                <VideoTile
                  key={student.studentId}
                  student={student}
                  selected={
                    student.studentId ===
                    selected?.studentId
                  }
                  onSelect={() => {
                    setSelectedId(student.studentId)
                    setPanel('monitoring')
                  }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Side panel */}

        {panel !== 'none' && (
          <div className="w-[320px] shrink-0 border-l border-white/10 bg-[#0f131e]">
            {panel === 'participants' && (
              <ParticipantsPanel students={students} />
            )}

            {panel === 'chat' && <ChatPanel />}

            {panel === 'monitoring' && selected && (
              <div className="dark h-full">
                <AIMonitoringPanel student={selected} />
              </div>
            )}

            {panel === 'monitoring' && !selected && (
              <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-white/60">
                <ShieldAlert className="h-6 w-6" />

                <p className="text-sm">
                  Select a student tile to view their AI
                  monitoring detail.
                </p>
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
        handRaised={false}
        screenSharing={screenSharing}
        recording
        onToggleMic={() =>
          setMicOn((value) => !value)
        }
        onToggleCamera={() =>
          setCameraOn((value) => !value)
        }
        onToggleHand={() => {}}
        onToggleScreenShare={() =>
          setScreenSharing((value) => !value)
        }
        onToggleParticipants={() =>
          setPanel((value) =>
            value === 'participants'
              ? 'none'
              : 'participants',
          )
        }
        onToggleChat={() =>
          setPanel((value) =>
            value === 'chat' ? 'none' : 'chat',
          )
        }
        onToggleMonitoring={() =>
          setPanel((value) =>
            value === 'monitoring'
              ? 'none'
              : 'monitoring',
          )
        }
        onLeave={() => endMutation.mutate()}
        leaveLabel="End class"
        timer={timer}
      />
    </div>
  )
}