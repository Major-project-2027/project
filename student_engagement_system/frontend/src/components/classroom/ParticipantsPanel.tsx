import { MicOff, Mic, Hand, ShieldAlert } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import type { StudentLiveState } from '@/types/domain'
import { engagementTone } from '@/lib/utils'

export function ParticipantsPanel({ students }: { students: StudentLiveState[] }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-4 py-3">
        <p className="text-sm font-semibold text-white">Participants ({students.length})</p>
      </div>
      <ul className="flex-1 space-y-1 overflow-y-auto p-2">
        {students.map((s) => {
          const tone = engagementTone(s.currentEngagement)
          return (
            <li key={s.studentId} className="flex items-center gap-2.5 rounded-lg px-2 py-2 hover:bg-white/5">
              <Avatar name={s.studentName} size={30} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-white">{s.studentName}</p>
                <p className="truncate text-[11px] capitalize text-white/50">{s.cognitiveState}</p>
              </div>
              {s.handRaised && <Hand className="h-3.5 w-3.5 shrink-0 text-attention-400" />}
              {!s.micOn ? <MicOff className="h-3.5 w-3.5 shrink-0 text-white/40" /> : <Mic className="h-3.5 w-3.5 shrink-0 text-white/40" />}
              {!s.authenticated && <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-critical-400" />}
              <Badge variant={tone} className="shrink-0">{s.currentEngagement}</Badge>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
