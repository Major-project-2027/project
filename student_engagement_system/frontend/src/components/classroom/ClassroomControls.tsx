import {
  Mic, MicOff, Video, VideoOff, ScreenShare, ScreenShareOff, Hand, PhoneOff,
  Users, MessageSquare, Activity, Circle, PenLine,
} from 'lucide-react'
import { cn } from '@/lib/utils'

function ControlButton({
  active,
  onClick,
  icon: Icon,
  label,
  disabled,
  highlight,
}: {
  active?: boolean
  onClick?: () => void
  icon: typeof Mic
  label: string
  disabled?: boolean
  highlight?: boolean
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      title={disabled ? `${label} (unavailable)` : label}
      disabled={disabled}
      className={cn(
        'flex h-11 w-11 items-center justify-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-40',
        highlight
          ? 'bg-focus-500 text-white hover:bg-focus-600'
          : active
            ? 'bg-white/15 text-white hover:bg-white/20'
            : 'bg-white/90 text-[#0f131e] hover:bg-white',
      )}
    >
      <Icon className="h-5 w-5" />
    </button>
  )
}

function PanelButton({
  active,
  onClick,
  icon: Icon,
  label,
  badge,
}: {
  active?: boolean
  onClick: () => void
  icon: typeof Mic
  label: string
  badge?: number
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      title={label}
      className={cn(
        'relative flex h-10 w-10 items-center justify-center rounded-full text-white/70 hover:bg-white/10',
        active && 'bg-white/15 text-white',
      )}
    >
      <Icon className="h-[18px] w-[18px]" />
      {!!badge && (
        <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-critical-500 px-1 text-[10px] font-semibold text-white">
          {badge > 9 ? '9+' : badge}
        </span>
      )}
    </button>
  )
}

export type ClassroomPanel = 'none' | 'participants' | 'chat' | 'monitoring'

/**
 * Bottom toolbar for the live classroom. Teacher-only tools (screen share,
 * whiteboard, AI monitoring, End class) are only rendered for the teacher;
 * the server enforces the same rules independently.
 */
export function ClassroomControls({
  role,
  micOn, cameraOn, handRaised, screenSharing, recording,
  micAvailable = true, cameraAvailable = true,
  whiteboardOpen, panel, unreadChat,
  onToggleMic, onToggleCamera, onToggleHand, onToggleScreenShare, onToggleWhiteboard,
  onTogglePanel, onLeave,
  timer,
  leaveLabel,
}: {
  role: 'teacher' | 'student'
  micOn: boolean
  cameraOn: boolean
  handRaised?: boolean
  screenSharing?: boolean
  recording: boolean
  micAvailable?: boolean
  cameraAvailable?: boolean
  whiteboardOpen?: boolean
  panel: ClassroomPanel
  unreadChat?: number
  onToggleMic: () => void
  onToggleCamera: () => void
  onToggleHand?: () => void
  onToggleScreenShare?: () => void
  onToggleWhiteboard?: () => void
  onTogglePanel: (panel: Exclude<ClassroomPanel, 'none'>) => void
  onLeave: () => void
  timer: string
  leaveLabel?: string
}) {
  const teacher = role === 'teacher'

  return (
    <div className="relative flex items-center justify-center gap-3 bg-[#0a0c14] px-4 py-3">
      {/* Left: timer / recording -- absolutely positioned so the pill stays centered */}
      <div className="absolute left-4 hidden items-center gap-2 text-xs font-medium text-white/70 sm:flex">
        {recording && <span className="flex items-center gap-1 text-critical-400"><Circle className="h-2 w-2 fill-current animate-pulse" />REC</span>}
        <span className="font-mono">{timer}</span>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2.5 rounded-full bg-[#1a1f2e] px-3 py-2 shadow-lg shadow-black/40">
        <ControlButton
          icon={micOn ? Mic : MicOff}
          active={micOn}
          disabled={!micAvailable}
          onClick={onToggleMic}
          label={micOn ? 'Mute microphone' : 'Unmute microphone'}
        />
        <ControlButton
          icon={cameraOn ? Video : VideoOff}
          active={cameraOn}
          disabled={!cameraAvailable}
          onClick={onToggleCamera}
          label={cameraOn ? 'Turn off camera' : 'Turn on camera'}
        />
        {!teacher && onToggleHand && (
          <ControlButton icon={Hand} active={handRaised} onClick={onToggleHand} label={handRaised ? 'Lower hand' : 'Raise hand'} />
        )}

        {teacher && (
          <>
            <ControlButton
              icon={screenSharing ? ScreenShareOff : ScreenShare}
              highlight={screenSharing}
              onClick={onToggleScreenShare}
              label={screenSharing ? 'Stop sharing' : 'Share screen'}
            />
            <ControlButton
              icon={PenLine}
              highlight={whiteboardOpen}
              onClick={onToggleWhiteboard}
              label={whiteboardOpen ? 'Close whiteboard' : 'Open whiteboard'}
            />
          </>
        )}

        <div className="mx-1 h-6 w-px bg-white/10" />

        <PanelButton icon={Users} active={panel === 'participants'} onClick={() => onTogglePanel('participants')} label="Participants" />
        <PanelButton icon={MessageSquare} active={panel === 'chat'} onClick={() => onTogglePanel('chat')} label="Chat" badge={unreadChat} />
        {teacher && (
          <PanelButton icon={Activity} active={panel === 'monitoring'} onClick={() => onTogglePanel('monitoring')} label="AI monitoring" />
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
