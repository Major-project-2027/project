// Camera / microphone / screen capture with honest, specific error states.
// Never fakes a device: whatever getUserMedia actually returned is what the
// UI and the WebRTC connection get.

export type MediaKind = 'camera' | 'microphone' | 'screen'

export function describeMediaError(error: unknown, kind: MediaKind): string {
  const name = (error as { name?: string } | null)?.name ?? ''
  const device = kind === 'screen' ? 'screen sharing' : kind

  switch (name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return kind === 'screen'
        ? 'Screen sharing was cancelled or blocked.'
        : `Permission to use your ${device} was denied. Allow it in the browser's site settings and try again.`
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return `No ${device} was found on this device.`
    case 'NotReadableError':
    case 'TrackStartError':
      return `Your ${device} is already in use by another application or tab.`
    case 'OverconstrainedError':
      return `Your ${device} doesn't support the requested settings.`
    case 'AbortError':
      return `Your ${device} couldn't be started.`
    case 'TypeError':
      return `Your ${device} isn't available in this browser (a secure https connection is required).`
    default:
      return `Couldn't access your ${device}.`
  }
}

export interface LocalMedia {
  stream: MediaStream
  videoTrack: MediaStreamTrack | null
  audioTrack: MediaStreamTrack | null
  cameraError: string | null
  micError: string | null
}

/**
 * Ask for camera + microphone together (one permission prompt), and if that
 * fails, retry each separately so one missing/blocked device doesn't take
 * the other down with it.
 */
export async function acquireLocalMedia(opts: { video: boolean; audio: boolean }): Promise<LocalMedia> {
  const stream = new MediaStream()
  let cameraError: string | null = null
  let micError: string | null = null

  if (!navigator.mediaDevices?.getUserMedia) {
    return {
      stream,
      videoTrack: null,
      audioTrack: null,
      cameraError: opts.video ? describeMediaError({ name: 'TypeError' }, 'camera') : null,
      micError: opts.audio ? describeMediaError({ name: 'TypeError' }, 'microphone') : null,
    }
  }

  try {
    const both = await navigator.mediaDevices.getUserMedia({ video: opts.video, audio: opts.audio })
    both.getTracks().forEach((t) => stream.addTrack(t))
  } catch {
    if (opts.video) {
      try {
        const v = await navigator.mediaDevices.getUserMedia({ video: true })
        v.getVideoTracks().forEach((t) => stream.addTrack(t))
      } catch (error) {
        cameraError = describeMediaError(error, 'camera')
      }
    }
    if (opts.audio) {
      try {
        const a = await navigator.mediaDevices.getUserMedia({ audio: true })
        a.getAudioTracks().forEach((t) => stream.addTrack(t))
      } catch (error) {
        micError = describeMediaError(error, 'microphone')
      }
    }
  }

  return {
    stream,
    videoTrack: stream.getVideoTracks()[0] ?? null,
    audioTrack: stream.getAudioTracks()[0] ?? null,
    cameraError,
    micError,
  }
}

/** A fresh camera track (used when turning the camera back on). */
export async function acquireCameraTrack(): Promise<MediaStreamTrack> {
  const s = await navigator.mediaDevices.getUserMedia({ video: true })
  return s.getVideoTracks()[0]
}
