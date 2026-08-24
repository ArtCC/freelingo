'use client'

import { useEffect, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { apiFetch } from '@/lib/api'
import { float32ToWav } from '@/lib/audio'

interface VoiceRecorderProps {
  studyPlanId: number
  onTranscription: (text: string) => void | Promise<void>
  maxSeconds?: number
  disabled?: boolean
  className?: string
}

type RecorderState = 'idle' | 'recording' | 'transcribing' | 'error'

interface RecordingContext {
  studyPlanId: number
  onTranscription: VoiceRecorderProps['onTranscription']
}

export function VoiceRecorder({
  studyPlanId,
  onTranscription,
  maxSeconds = 5,
  disabled = false,
  className = '',
}: VoiceRecorderProps) {
  const [state, setState] = useState<RecorderState>('idle')
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const chunksRef = useRef<Float32Array[]>([])
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const errorResetRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const requestAbortRef = useRef<AbortController | null>(null)
  const recordingContextRef = useRef<RecordingContext | null>(null)
  const mountedRef = useRef(true)
  const t = useTranslations('voiceRecorder')

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (autoStopRef.current) clearTimeout(autoStopRef.current)
      if (errorResetRef.current) clearTimeout(errorResetRef.current)
      processorRef.current?.disconnect()
      processorRef.current = null
      void audioCtxRef.current?.close()
      audioCtxRef.current = null
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      recordingContextRef.current = null
      requestAbortRef.current?.abort()
      requestAbortRef.current = null
    }
  }, [])

  function cleanupAudio() {
    if (autoStopRef.current) {
      clearTimeout(autoStopRef.current)
      autoStopRef.current = null
    }
    processorRef.current?.disconnect()
    processorRef.current = null
    void audioCtxRef.current?.close()
    audioCtxRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }

  function showError() {
    if (!mountedRef.current) return
    setState('error')
    if (errorResetRef.current) clearTimeout(errorResetRef.current)
    errorResetRef.current = setTimeout(() => {
      if (mountedRef.current) setState('idle')
      errorResetRef.current = null
    }, 2000)
  }

  async function processAndSend(inputRate: number, context: RecordingContext) {
    let controller: AbortController | null = null
    try {
      const chunks = chunksRef.current
      chunksRef.current = []

      if (chunks.length === 0) {
        showError()
        return
      }

      if (!mountedRef.current) return
      setState('transcribing')

      const totalLength = chunks.reduce((sum, c) => sum + c.length, 0)
      const combined = new Float32Array(totalLength)
      let offset = 0
      for (const chunk of chunks) {
        combined.set(chunk, offset)
        offset += chunk.length
      }

      let samples = combined
      if (inputRate !== 16000) {
        const offlineCtx = new OfflineAudioContext(
          1,
          Math.ceil((combined.length * 16000) / inputRate),
          16000
        )
        const buffer = offlineCtx.createBuffer(1, combined.length, inputRate)
        buffer.getChannelData(0).set(combined)
        const source = offlineCtx.createBufferSource()
        source.buffer = buffer
        source.connect(offlineCtx.destination)
        source.start(0)
        const rendered = await offlineCtx.startRendering()
        samples = rendered.getChannelData(0)
      }

      if (!mountedRef.current) return
      const wav = float32ToWav(samples, 16000)
      const formData = new FormData()
      formData.append(
        'audio',
        new Blob([wav], { type: 'audio/wav' }),
        'recording.wav'
      )
      formData.append('study_plan_id', String(context.studyPlanId))

      controller = new AbortController()
      requestAbortRef.current = controller
      const res = await apiFetch('/api/stt', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`STT error ${res.status}`)
      const { text } = (await res.json()) as { text: string }
      if (!mountedRef.current) return
      await context.onTranscription(text)
      if (mountedRef.current) setState('idle')
    } catch {
      showError()
    } finally {
      if (requestAbortRef.current === controller) {
        requestAbortRef.current = null
      }
    }
  }

  function stopRecording() {
    const context = recordingContextRef.current
    if (!context) return
    recordingContextRef.current = null
    if (!streamRef.current) {
      chunksRef.current = []
      if (mountedRef.current) setState('idle')
      return
    }
    const sampleRate = audioCtxRef.current?.sampleRate || 48000
    cleanupAudio()
    void processAndSend(sampleRate, context)
  }

  async function startRecording() {
    const context = { studyPlanId, onTranscription }
    recordingContextRef.current = context
    chunksRef.current = []
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      if (!mountedRef.current || recordingContextRef.current !== context) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      streamRef.current = stream

      const audioCtx = new AudioContext()
      audioCtxRef.current = audioCtx

      const source = audioCtx.createMediaStreamSource(stream)
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0)
        chunksRef.current.push(new Float32Array(input))
      }

      source.connect(processor)
      processor.connect(audioCtx.destination)

      autoStopRef.current = setTimeout(() => {
        stopRecording()
      }, maxSeconds * 1000)
    } catch {
      const isCurrentRecording = recordingContextRef.current === context
      if (isCurrentRecording) {
        recordingContextRef.current = null
        cleanupAudio()
        showError()
      }
    }
  }

  async function handleClick() {
    if (disabled) return

    if (state === 'recording') {
      stopRecording()
      return
    }

    if (state !== 'idle') return

    setState('recording')
    await startRecording()
  }

  const label =
    state === 'recording'
      ? `■ ${t('stop')}`
      : state === 'transcribing'
        ? `... ${t('processing')}`
        : state === 'error'
          ? `✕ ${t('error')}`
          : `● ${t('record')}`

  const colorClass =
    state === 'recording'
      ? 'border-fl-error/60 text-fl-error-fg animate-pulse'
      : state === 'transcribing'
        ? 'border-fl-border text-fl-muted-3 animate-pulse'
        : state === 'error'
          ? 'border-fl-error/40 text-fl-error-fg'
          : disabled
            ? 'border-fl-border text-fl-muted-4 cursor-not-allowed opacity-40'
            : 'border-fl-border text-fl-muted-2 hover:border-fl-border-2 hover:text-fl-fg'

  return (
    <button
      onClick={handleClick}
      disabled={disabled && state === 'idle'}
      aria-label={state === 'recording' ? t('ariaStop') : t('ariaRecord')}
      className={`border px-3 py-2 font-mono text-xs tracking-widest uppercase transition-colors ${colorClass} ${className}`}
    >
      {label}
    </button>
  )
}
