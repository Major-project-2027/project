import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ScreenShare, ShieldCheck } from 'lucide-react'
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
  const classQuery = useQuery({ queryKey: ['class', classId], queryFn: () => classesApi.get(classId ?? '') })
  const [micOn, setMicOn] = useState(false)
  const [cameraOn, setCameraOn] = useState(true)
  const [handRaised, setHandRaised] = useState(false)
  const [panel, setPanel] = useState<SidePanel>('none')
  const [seconds, setSeconds] = useState(0)
  const [myEngagement, setMyEngagement] = useState(74)
  const students = generateLiveStudents(15)

  useEffect(() => {
    const t = setInterval(() => {
      setSeconds((s) => s + 1)
      setMyEngagement((e) => Math.max(20, Math.min(98, e + Math.round((Math.random() - 0.5) * 6))))
    }, 1000)
    return () => clearInterval(t)
  }, [])

  const timer = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <div className="flex h-screen flex-col bg-[#0a0c14]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-xs font-medium text-critical-400"><span className="h-2 w-2 rounded-full bg-critical-500 animate-pulse" />LIVE</span>
          <p className="text-sm font-semibold text-white">{classQuery.data?.title ?? 'Live class'}</p>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-engaged-500/15 px-3 py-1 text-xs font-medium text-engaged-400">
          <ShieldCheck className="h-3.5 w-3.5" />Face verified
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col gap-3 p-3">
          {/* Teacher's video, large */}
          <div className="relative flex flex-1 items-center justify-center rounded-2xl bg-gradient-to-br from-focus-900/60 to-[#0f131e]">
            <Avatar name="Dr. Kavita Rao" size={72} />
            <div className="absolute left-3 top-3 rounded-md bg-black/50 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">Dr. Kavita Rao (Teacher)</div>
            <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md bg-black/50 px-2.5 py-1 text-xs text-white backdrop-blur"><ScreenShare className="h-3.5 w-3.5" />Screen not shared</div>
          </div>

          {/* Self tile + engagement */}
          <div className="flex items-center justify-between rounded-2xl bg-[#12151f] p-3">
            <div className="flex items-center gap-3">
              <Avatar name={currentStudent.name} size={44} />
              <div>
                <p className="text-sm font-medium text-white">{currentStudent.name} (You)</p>
                <p className="text-xs text-white/50">{cameraOn ? 'Camera on' : 'Camera off'} · {micOn ? 'Mic on' : 'Mic muted'}</p>
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

        {panel !== 'none' && (
          <div className="w-[320px] shrink-0 border-l border-white/10 bg-[#0f131e]">
            {panel === 'participants' && <ParticipantsPanel students={students} />}
            {panel === 'chat' && <ChatPanel />}
          </div>
        )}
      </div>

      <ClassroomControls
        role="student"
        micOn={micOn} cameraOn={cameraOn} handRaised={handRaised} screenSharing={false} recording={false}
        onToggleMic={() => setMicOn((v) => !v)}
        onToggleCamera={() => setCameraOn((v) => !v)}
        onToggleHand={() => setHandRaised((v) => !v)}
        onToggleScreenShare={() => {}}
        onToggleParticipants={() => setPanel((p) => (p === 'participants' ? 'none' : 'participants'))}
        onToggleChat={() => setPanel((p) => (p === 'chat' ? 'none' : 'chat'))}
        onLeave={() => navigate('/student')}
        timer={timer}
      />
    </div>
  )
}
