// Temporary WebRTC diagnostics for the live classroom. Logs only media
// shape and connection state -- never SDP bodies, ICE addresses or tokens.

export function rtcLog(tag: string, ...details: unknown[]) {
  console.info(`[${tag}]`, ...details)
}

/** Which media sections (m=audio / m=video) an SDP carries, with direction. */
export function describeSdp(sdp: string | undefined | null) {
  if (!sdp) return []
  const sections: { kind: string; direction: string }[] = []
  for (const block of sdp.split(/\r?\nm=/).slice(1)) {
    const kind = block.split(' ')[0]
    const direction = /a=(sendrecv|sendonly|recvonly|inactive)/.exec(block)?.[1] ?? 'sendrecv'
    sections.push({ kind, direction })
  }
  return sections
}

export function describeTrack(track: MediaStreamTrack | null | undefined) {
  if (!track) return null
  return { kind: track.kind, enabled: track.enabled, muted: track.muted, readyState: track.readyState }
}

/** Log every state transition of a peer connection under one label. */
export function watchPeerStates(peer: RTCPeerConnection, label: string) {
  const log = () =>
    rtcLog('WEBRTC', label, {
      connectionState: peer.connectionState,
      iceConnectionState: peer.iceConnectionState,
      signalingState: peer.signalingState,
    })
  peer.addEventListener('connectionstatechange', log)
  peer.addEventListener('iceconnectionstatechange', log)
  peer.addEventListener('signalingstatechange', log)
}

/**
 * Once connected: are video frames actually arriving, and over which kind
 * of ICE path (host / srflx / relay)? Distinguishes "no connectivity" from
 * "connected but the <video> element isn't rendering".
 */
export async function logInboundStats(peer: RTCPeerConnection, label: string) {
  try {
    const stats = await peer.getStats()
    let video: Record<string, unknown> | null = null
    let audio: Record<string, unknown> | null = null
    let pairId: string | undefined
    const byId = new Map<string, any>()
    stats.forEach((report: any) => {
      byId.set(report.id, report)
      if (report.type === 'inbound-rtp' && report.kind === 'video') {
        video = { bytesReceived: report.bytesReceived, framesDecoded: report.framesDecoded, frameWidth: report.frameWidth }
      }
      if (report.type === 'inbound-rtp' && report.kind === 'audio') {
        audio = { bytesReceived: report.bytesReceived }
      }
      if (report.type === 'transport' && report.selectedCandidatePairId) {
        pairId = report.selectedCandidatePairId
      }
    })
    const pair = pairId ? byId.get(pairId) : null
    const path = pair
      ? {
          local: byId.get(pair.localCandidateId)?.candidateType,
          remote: byId.get(pair.remoteCandidateId)?.candidateType,
        }
      : null
    rtcLog('WEBRTC', label, 'inbound', { video, audio, path })
  } catch (error) {
    console.warn('[WEBRTC] getStats failed', error)
  }
}
