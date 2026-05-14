'use client'

import { useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { useAuthStore } from '@/store/auth'

interface AudioPlayerProps {
  text: string
  voice?: string
  size?: 'sm' | 'md'
  className?: string
}

type PlayerState = 'idle' | 'loading' | 'playing' | 'error'

/** Returns true if the browser can play streaming MP3 via MediaSource Extensions. */
function supportsMediaSourceMp3(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.MediaSource !== 'undefined' &&
    MediaSource.isTypeSupported('audio/mpeg')
  )
}

export function AudioPlayer({ text, voice, size = 'sm', className = '' }: AudioPlayerProps) {
  const [state, setState] = useState<PlayerState>('idle')
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const msRef = useRef<MediaSource | null>(null)
  const cancelledRef = useRef(false)
  const accessToken = useAuthStore((s) => s.accessToken)
  const t = useTranslations('audioPlayer')

  /** Stop and clean up any in-progress playback. */
  function cleanup(): void {
    cancelledRef.current = true
    if (msRef.current?.readyState === 'open') {
      try {
        msRef.current.endOfStream()
      } catch {
        /* already closed */
      }
    }
    msRef.current = null
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
      audioRef.current = null
    }
  }

  async function handleClick() {
    if (state === 'loading') return

    if (state === 'playing') {
      cleanup()
      setState('idle')
      return
    }

    cancelledRef.current = false
    setState('loading')

    try {
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ text, voice }),
      })
      if (!res.ok) throw new Error(`TTS error ${res.status}`)

      if (supportsMediaSourceMp3() && res.body) {
        await playStreaming(res.body)
      } else {
        await playBlob(res)
      }
    } catch {
      if (cancelledRef.current) return
      setState('error')
      setTimeout(() => setState('idle'), 2000)
    }
  }

  /**
   * Stream MP3 into a MediaSource so playback starts as soon as the first
   * chunks arrive — before the entire audio file has been downloaded.
   */
  async function playStreaming(body: ReadableStream<Uint8Array>): Promise<void> {
    const ms = new MediaSource()
    msRef.current = ms
    const audio = new Audio()
    audioRef.current = audio
    const objectUrl = URL.createObjectURL(ms)
    audio.src = objectUrl

    try {
      await new Promise<void>((resolve, reject) => {
        ms.addEventListener(
          'sourceopen',
          () => {
            let sb: SourceBuffer
            try {
              sb = ms.addSourceBuffer('audio/mpeg')
            } catch (e) {
              reject(e)
              return
            }

            // Start playback as soon as enough data is buffered
            audio.addEventListener(
              'canplay',
              () => {
                if (!cancelledRef.current && audio.paused) {
                  setState('playing')
                  audio.play().catch(() => {/* autoplay policy — handled gracefully */})
                }
              },
              { once: true },
            )

            const reader = body.getReader()

            const pump = async (): Promise<void> => {
              for (;;) {
                if (cancelledRef.current) {
                  resolve()
                  return
                }

                let result: ReadableStreamReadResult<Uint8Array>
                try {
                  result = await reader.read()
                } catch {
                  // Stream cancelled (e.g. user clicked stop) — resolve cleanly
                  resolve()
                  return
                }

                if (result.done || cancelledRef.current) {
                  if (!cancelledRef.current && ms.readyState === 'open') {
                    try {
                      ms.endOfStream()
                    } catch {/* ignore */}
                  }
                  resolve()
                  return
                }

                // Wait for SourceBuffer to be ready before appending
                if (sb.updating) {
                  await new Promise<void>((r) =>
                    sb.addEventListener('updateend', () => r(), { once: true }),
                  )
                }
                if (cancelledRef.current) {
                  resolve()
                  return
                }

                await new Promise<void>((r, e) => {
                  sb.addEventListener('updateend', () => r(), { once: true })
                  sb.addEventListener('error', () => e(new Error('SourceBuffer error')), { once: true })
                  // Slice to a plain ArrayBuffer to satisfy strict BufferSource typing
                  const buf = result.value.buffer.slice(
                    result.value.byteOffset,
                    result.value.byteOffset + result.value.byteLength,
                  )
                  sb.appendBuffer(buf as ArrayBuffer)
                })
              }
            }

            pump().catch(reject)
          },
          { once: true },
        )

        ms.addEventListener('error', () => reject(new Error('MediaSource error')), { once: true })
      })

      // Wait for audio to finish playing (only if not cancelled)
      if (!cancelledRef.current) {
        await new Promise<void>((resolve) => {
          audio.onended = () => resolve()
          // Resolve on error too so we don't hang
          audio.onerror = () => resolve()
        })
      }
    } finally {
      URL.revokeObjectURL(objectUrl)
      audioRef.current = null
      msRef.current = null
      if (!cancelledRef.current) setState('idle')
    }
  }

  /** Fallback: download the full blob then play (used when MSE is unavailable). */
  async function playBlob(res: Response): Promise<void> {
    const blob = await res.blob()
    if (cancelledRef.current) return
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audioRef.current = audio
    setState('playing')
    await audio.play()
    audio.onended = () => {
      URL.revokeObjectURL(url)
      audioRef.current = null
      setState('idle')
    }
    audio.onerror = () => {
      URL.revokeObjectURL(url)
      audioRef.current = null
      if (cancelledRef.current) return
      setState('error')
      setTimeout(() => setState('idle'), 2000)
    }
  }

  const sizeClass = size === 'sm' ? 'px-2 py-1 text-fl-hint' : 'px-3 py-2 text-xs'

  const label =
    state === 'loading' ? '…' :
    state === 'playing' ? '■' :
    state === 'error'   ? '✕' : '▶'

  const colorClass =
    state === 'playing' ? 'border-fl-border-2 text-fl-fg' :
    state === 'loading' ? 'border-fl-border text-fl-muted-3 animate-pulse' :
    state === 'error'   ? 'border-fl-error/40 text-fl-error-fg' :
    'border-fl-border text-fl-muted-2 hover:border-fl-border-2 hover:text-fl-fg'

  return (
    <button
      onClick={handleClick}
      title={state === 'playing' ? t('stop') : t('listen')}
      aria-label={state === 'playing' ? t('ariaStop') : t('ariaListen')}
      className={`border font-mono tracking-widest uppercase transition-colors ${colorClass} ${sizeClass} ${className}`}
    >
      {label}
    </button>
  )
}
