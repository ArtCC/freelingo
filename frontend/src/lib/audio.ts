/**
 * Streaming TTS player for the conversation WebSocket.
 *
 * Protocol (backend → frontend):
 *   {"type":"tts_stream_start"}  — audio begins; call start(onEnded)
 *   <binary frames>              — raw MP3 chunks; call appendChunk() for each
 *   {"type":"tts_stream_end"}    — no more chunks; call end()
 *   cancel()                     — barge-in / session stop
 *
 * Primary path: MediaSource Extensions + <audio> element (true streaming,
 * ~300–500 ms lower latency with OpenAI TTS).
 * Fallback path: Web Audio API — accumulates all chunks then decodes the
 * complete MP3 on tts_stream_end (identical latency to the old approach, used
 * only when the browser cannot play audio/mpeg via MSE).
 */
export interface ConvStreamPlayer {
  /** Set up playback pipeline for the current turn.  Call on tts_stream_start. */
  start(onEnded: () => void): void
  /** Forward one raw MP3 binary frame received from the WebSocket. */
  appendChunk(chunk: ArrayBuffer): void
  /** Signal end-of-stream for the current turn.  Call on tts_stream_end. */
  end(): void
  /** Immediately halt playback and release resources (barge-in / stop). */
  cancel(): void
}

/** Factory — picks MSE or Web-Audio-fallback depending on browser capability. */
export function createConvStreamPlayer(): ConvStreamPlayer {
  const mseSupported =
    typeof window !== 'undefined' &&
    typeof window.MediaSource !== 'undefined' &&
    MediaSource.isTypeSupported('audio/mpeg')
  return mseSupported ? _createMSEPlayer() : _createFallbackPlayer()
}

// ---------------------------------------------------------------------------
// MSE implementation
// ---------------------------------------------------------------------------
function _createMSEPlayer(): ConvStreamPlayer {
  let ms: MediaSource | null = null
  let sb: SourceBuffer | null = null
  let audio: HTMLAudioElement | null = null
  let objectUrl = ''
  let cancelled = false
  let onEndedCb: (() => void) | null = null
  // Chunks queued while SourceBuffer is busy or not yet open
  const pending: ArrayBuffer[] = []
  // Set to true once end() is called so we know to call endOfStream after drain
  let eosRequested = false

  function _tryFlush(): void {
    if (cancelled || !ms || ms.readyState !== 'open') return
    if (!sb || sb.updating) return

    if (pending.length > 0) {
      const chunk = pending.shift()!
      try {
        sb.appendBuffer(chunk)
      } catch {
        // QuotaExceededError or InvalidStateError — skip and try next
        _tryFlush()
      }
      return
    }

    if (eosRequested) {
      eosRequested = false
      try { ms.endOfStream() } catch { /* already closed */ }
    }
  }

  function start(onEnded: () => void): void {
    cancelled = false
    eosRequested = false
    onEndedCb = onEnded
    pending.length = 0

    ms = new MediaSource()
    objectUrl = URL.createObjectURL(ms)
    audio = new Audio()
    audio.src = objectUrl
    audio.preload = 'auto'

    audio.addEventListener(
      'canplay',
      () => {
        if (!cancelled && audio) {
          audio.play().catch((err: unknown) => {
            // play() was blocked (autoplay policy, codec issue, etc.).
            // Notify the caller so the UI does not get stuck in "speaking" state.
            console.warn('[audio] play() rejected — no audio output:', err)
            onEndedCb?.()
          })
        }
      },
      { once: true },
    )
    audio.addEventListener('ended', () => { onEndedCb?.() }, { once: true })
    audio.addEventListener('error', () => { onEndedCb?.() }, { once: true })

    ms.addEventListener(
      'sourceopen',
      () => {
        if (cancelled || !ms) return
        try {
          sb = ms.addSourceBuffer('audio/mpeg')
          sb.addEventListener('updateend', _tryFlush)
          _tryFlush() // drain chunks that arrived before sourceopen
        } catch {
          onEndedCb?.()
        }
      },
      { once: true },
    )
    ms.addEventListener('error', () => { onEndedCb?.() }, { once: true })
  }

  function appendChunk(chunk: ArrayBuffer): void {
    if (cancelled) return
    pending.push(chunk)
    _tryFlush()
  }

  function end(): void {
    if (cancelled) return
    eosRequested = true
    _tryFlush()
  }

  function cancel(): void {
    // Null the callback first — prevents spurious calls triggered by src reset
    onEndedCb = null
    cancelled = true
    pending.length = 0
    eosRequested = false

    if (sb) {
      try { sb.removeEventListener('updateend', _tryFlush) } catch { /* ignore */ }
      sb = null
    }
    if (ms?.readyState === 'open') {
      try { ms.endOfStream() } catch { /* ignore */ }
    }
    ms = null

    if (audio) {
      try { audio.pause() } catch { /* ignore */ }
      audio.src = ''
      audio = null
    }

    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = ''
    }
  }

  return { start, appendChunk, end, cancel }
}

// ---------------------------------------------------------------------------
// Fallback: Web Audio API — accumulate chunks, decode complete MP3 on end()
// ---------------------------------------------------------------------------
function _createFallbackPlayer(): ConvStreamPlayer {
  const chunks: ArrayBuffer[] = []
  const sources: AudioBufferSourceNode[] = []
  let audioCtx: AudioContext | null = null
  let nextTime = 0
  let onEndedCb: (() => void) | null = null
  let cancelled = false

  function start(onEnded: () => void): void {
    cancelled = false
    chunks.length = 0
    sources.length = 0
    nextTime = 0
    onEndedCb = onEnded
    try { audioCtx = new AudioContext() } catch { audioCtx = null }
  }

  function appendChunk(chunk: ArrayBuffer): void {
    if (!cancelled) chunks.push(chunk)
  }

  function end(): void {
    if (cancelled || !audioCtx || chunks.length === 0) { onEndedCb?.(); return }
    const totalBytes = chunks.reduce((n, c) => n + c.byteLength, 0)
    const combined = new Uint8Array(totalBytes)
    let offset = 0
    for (const c of chunks) { combined.set(new Uint8Array(c), offset); offset += c.byteLength }
    chunks.length = 0

    const ctx = audioCtx
    void ctx.decodeAudioData(combined.buffer).then((decoded) => {
      if (cancelled || !ctx) return
      const src = ctx.createBufferSource()
      src.buffer = decoded
      src.connect(ctx.destination)
      const startAt = Math.max(ctx.currentTime + 0.025, nextTime)
      src.start(startAt)
      nextTime = startAt + decoded.duration
      sources.push(src)
      src.onended = () => {
        const i = sources.indexOf(src)
        if (i !== -1) sources.splice(i, 1)
        if (sources.length === 0) onEndedCb?.()
      }
    }).catch(() => onEndedCb?.())
  }

  function cancel(): void {
    onEndedCb = null
    cancelled = true
    chunks.length = 0
    for (const s of sources) { try { s.stop(0) } catch { /* already stopped */ } }
    sources.length = 0
    nextTime = 0
    audioCtx?.close()
    audioCtx = null
  }

  return { start, appendChunk, end, cancel }
}

// ---------------------------------------------------------------------------

/**
 * Encodes a Float32Array of mono PCM samples into a standard WAV ArrayBuffer.
 * VAD delivers samples at 16 000 Hz; STT service accepts audio/wav.
 */
export function float32ToWav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const numChannels = 1
  const bitsPerSample = 16
  const blockAlign = numChannels * (bitsPerSample / 8)
  const byteRate = sampleRate * blockAlign
  const dataSize = samples.length * blockAlign
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  function writeStr(offset: number, s: string) {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i))
  }

  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)            // PCM chunk size
  view.setUint16(20, 1, true)             // PCM format
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, byteRate, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitsPerSample, true)
  writeStr(36, 'data')
  view.setUint32(40, dataSize, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    offset += 2
  }

  return buffer
}

export interface AudioQueue {
  enqueue: (arrayBuffer: ArrayBuffer) => Promise<void>
  cancel: () => void
}

/**
 * Creates a gapless audio playback queue backed by the Web Audio API.
 * Each ArrayBuffer is decoded (MP3/WAV/OGG accepted) and scheduled to play
 * immediately after the previous chunk, avoiding gaps between TTS segments.
 *
 * The AudioContext must be created during a user gesture to satisfy browser
 * autoplay policies.
 */
export function createAudioQueue(ctx: AudioContext): AudioQueue {
  // nextTime tracks when the next chunk should start (in AudioContext time).
  // Using a closure variable (not module-level) so multiple instances are safe.
  let nextTime = 0
  const sources: AudioBufferSourceNode[] = []
  // Serialize decoding+scheduling so that chunks are always played in the
  // exact order they were enqueued, regardless of how long decodeAudioData
  // takes for each chunk. Without this, a short chunk 2 could decode faster
  // than chunk 1 and get scheduled first, causing out-of-order playback.
  let chain: Promise<void> = Promise.resolve()

  async function _decode(arrayBuffer: ArrayBuffer): Promise<void> {
    // Resume context if it was suspended (can happen on iOS Safari)
    if (ctx.state === 'suspended') {
      await ctx.resume()
    }

    // Copy the buffer: decodeAudioData may detach the original ArrayBuffer
    const decoded = await ctx.decodeAudioData(arrayBuffer.slice(0))

    const source = ctx.createBufferSource()
    source.buffer = decoded
    source.connect(ctx.destination)

    // Schedule with a small lead to avoid underrun; never schedule in the past
    const startAt = Math.max(ctx.currentTime + 0.025, nextTime)
    source.start(startAt)
    nextTime = startAt + decoded.duration

    sources.push(source)
    source.onended = () => {
      const idx = sources.indexOf(source)
      if (idx !== -1) sources.splice(idx, 1)
    }
  }

  function enqueue(arrayBuffer: ArrayBuffer): Promise<void> {
    chain = chain.then(() => _decode(arrayBuffer))
    return chain
  }

  function cancel(): void {
    for (const s of sources) {
      try {
        s.stop(0)
      } catch {
        // already stopped — ignore
      }
    }
    sources.length = 0
    nextTime = 0
    // Reset the chain so the queue is clean after a cancel
    chain = Promise.resolve()
  }

  return { enqueue, cancel }
}
