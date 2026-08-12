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
import { AlertToastStack, pushAlertToast } from '@/components/monitoring/AlertToast'
import { monitoringApi, classesApi } from '@/services/api/endpoints'
import { Badge } from '@/components/ui/Badge'

type SidePanel = 'none' | 'participants' | 'chat' | 'monitoring'

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
  const alertedIds = useRef<Set<string>>(new Set())

  const classQuery = useQuery({ queryKey: ['class', classId], queryFn: () => classesApi.get(classId ?? '') })
  const studentsQuery = useQuery({ queryKey: ['live-students', classId], queryFn: monitoringApi.liveStudents, refetchInterval: 8000 })
  const students = studentsQuery.data ?? []
  const selected = students.find((s) => s.studentId === selectedId) ?? students[0]
  const avgEngagement = Math.round(students.reduce((a, s) => a + s.currentEngagement, 0) / (students.length || 1))
  const activeAlerts = students.filter((s) => s.activeAlert)

  const endMutation = useMutation({
    mutationFn: () => classesApi.end(classId ?? ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classes'] })
      navigate('/teacher')
    },
  })

  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])

  // Fire a real-time toast the moment a NEW student alert appears — this is
  // the active "the teacher must be alerted" signal, separate from the
  // passive summary banner below.
  useEffect(() => {
    for (const s of students) {
      if (s.activeAlert && !alertedIds.current.has(s.studentId + s.activeAlert)) {
        alertedIds.current.add(s.studentId + s.activeAlert)
        pushAlertToast({
          studentName: s.studentName,
          message: ALERT_LABEL[s.activeAlert] ?? 'Attention issue detected',
          severity: s.activeAlert === 'phone_detected' || s.activeAlert === 'multiple_person' || s.activeAlert === 'face_auth_failed' ? 'critical' : 'warning',
        })
      }
    }
  }, [studentsQuery.data])

  const timer = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <div className="flex h-screen flex-col bg-[#0a0c14]">
      <AlertToastStack />

      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-xs font-medium text-critical-400"><span className="h-2 w-2 rounded-full bg-critical-500 animate-pulse" />LIVE</span>
          <p className="text-sm font-semibold text-white">{classQuery.data?.title ?? 'Live class'}</p>
          <Badge variant="neutral" className="bg-white/10 text-white">{students.length} students</Badge>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 sm:flex">
            <ConfidenceRing value={avgEngagement} size={36} strokeWidth={4} />
            <span className="text-xs text-white/60">class avg.</span>
          </div>
        </div>
      </div>

      {/* Alert banner — persistent summary, in addition to the live toasts */}
      {activeAlerts.length > 0 && !dismissedAlert && (
        <div className="flex items-center justify-between gap-3 bg-critical-500/15 px-4 py-2 text-sm text-critical-300">
          <span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />{activeAlerts.length} student(s) currently need attention — {activeAlerts[0].studentName} ({ALERT_LABEL[activeAlerts[0].activeAlert ?? ''] ?? 'flagged'})</span>
          <button onClick={() => setDismissedAlert(true)}><X className="h-4 w-4" /></button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Video grid */}
        <div className="flex-1 overflow-y-auto p-3">
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {students.map((s) => (
              <VideoTile key={s.studentId} student={s} selected={s.studentId === selected?.studentId} onSelect={() => { setSelectedId(s.studentId); setPanel('monitoring') }} />
            ))}
          </div>
        </div>

        {/* Side panel */}
        {panel !== 'none' && (
          <div className="w-[320px] shrink-0 border-l border-white/10 bg-[#0f131e]">
            {panel === 'participants' && <ParticipantsPanel students={students} />}
            {panel === 'chat' && <ChatPanel />}
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

      <ClassroomControls
        role="teacher"
        micOn={micOn} cameraOn={cameraOn} handRaised={false} screenSharing={screenSharing} recording
        onToggleMic={() => setMicOn((v) => !v)}
        onToggleCamera={() => setCameraOn((v) => !v)}
        onToggleHand={() => {}}
        onToggleScreenShare={() => setScreenSharing((v) => !v)}
        onToggleParticipants={() => setPanel((p) => (p === 'participants' ? 'none' : 'participants'))}
        onToggleChat={() => setPanel((p) => (p === 'chat' ? 'none' : 'chat'))}
        onToggleMonitoring={() => setPanel((p) => (p === 'monitoring' ? 'none' : 'monitoring'))}
        onLeave={() => endMutation.mutate()}
        leaveLabel="End class"
        timer={timer}
      />
    </div>
  )
}
