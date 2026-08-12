import {
  Mic, MicOff, Video, VideoOff, ScreenShare, Hand, PhoneOff,
  Users, MessageSquare, Activity, Circle,
} from 'lucide-react'
import { cn } from '@/lib/utils'

function ControlButton({
  active,
  danger,
  onClick,
  icon: Icon,
  label,
}: {
  active?: boolean
  danger?: boolean
  onClick?: () => void
  icon: typeof Mic
  label: string
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        'flex h-11 w-11 items-center justify-center rounded-full transition-colors',
        danger
          ? 'bg-critical-500 text-white hover:bg-critical-600'
          : active
            ? 'bg-white/15 text-white hover:bg-white/20'
            : 'bg-white/90 text-[#0f131e] hover:bg-white',
      )}
    >
      <Icon className="h-5 w-5" />
    </button>
  )
}

export function ClassroomControls({
  role,
  micOn, cameraOn, handRaised, screenSharing, recording,
  onToggleMic, onToggleCamera, onToggleHand, onToggleScreenShare,
  onToggleParticipants, onToggleChat, onToggleMonitoring, onLeave,
  timer,
  leaveLabel,
}: {
  role: 'teacher' | 'student'
  micOn: boolean
  cameraOn: boolean
  handRaised: boolean
  screenSharing: boolean
  recording: boolean
  onToggleMic: () => void
  onToggleCamera: () => void
  onToggleHand: () => void
  onToggleScreenShare: () => void
  onToggleParticipants: () => void
  onToggleChat: () => void
  onToggleMonitoring?: () => void
  onLeave: () => void
  timer: string
  leaveLabel?: string
}) {
  return (
    <div className="relative flex items-center justify-center gap-3 bg-[#0a0c14] px-4 py-3">
      {/* Left: timer / recording — absolutely positioned so the pill stays centered */}
      <div className="absolute left-4 hidden items-center gap-2 text-xs font-medium text-white/70 sm:flex">
        {recording && <span className="flex items-center gap-1 text-critical-400"><Circle className="h-2 w-2 fill-current animate-pulse" />REC</span>}
        <span className="font-mono">{timer}</span>
      </div>

      {/* Center: floating pill, Meet-style */}
      <div className="flex items-center gap-2.5 rounded-full bg-[#1a1f2e] px-3 py-2 shadow-lg shadow-black/40">
        <ControlButton icon={micOn ? Mic : MicOff} active={micOn} onClick={onToggleMic} label={micOn ? 'Mute' : 'Unmute'} />
        <ControlButton icon={cameraOn ? Video : VideoOff} active={cameraOn} onClick={onToggleCamera} label={cameraOn ? 'Turn off camera' : 'Turn on camera'} />
        {role === 'student' && <ControlButton icon={Hand} active={handRaised} onClick={onToggleHand} label="Raise hand" />}
        <ControlButton icon={ScreenShare} active={screenSharing} onClick={onToggleScreenShare} label="Share screen" />

        <div className="mx-1 h-6 w-px bg-white/10" />

        <button onClick={onToggleParticipants} className="flex h-10 w-10 items-center justify-center rounded-full text-white/70 hover:bg-white/10" title="Participants"><Users className="h-[18px] w-[18px]" /></button>
        <button onClick={onToggleChat} className="flex h-10 w-10 items-center justify-center rounded-full text-white/70 hover:bg-white/10" title="Chat"><MessageSquare className="h-[18px] w-[18px]" /></button>
        {role === 'teacher' && onToggleMonitoring && (
          <button onClick={onToggleMonitoring} className="flex h-10 w-10 items-center justify-center rounded-full text-white/70 hover:bg-white/10" title="AI Monitoring"><Activity className="h-[18px] w-[18px]" /></button>
        )}

        <div className="mx-1 h-6 w-px bg-white/10" />

        <button
          onClick={onLeave}
          className="flex h-11 items-center gap-2 rounded-full bg-critical-500 px-4 text-sm font-medium text-white hover:bg-critical-600"
        >
          <PhoneOff className="h-[18px] w-[18px]" />
          <span className="hidden sm:inline">{leaveLabel ?? 'Leave'}</span>
        </button>
      </div>
    </div>
  )
}
